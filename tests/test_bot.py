"""Offline checks of real Pipecat constructors and receptionist call lifecycle."""

import asyncio
import socket
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot
from config import load_config
from store import Store
from tools import ClinicTools


async def test_actual_pipecat_service_constructors_do_not_connect(monkeypatch):
    from pipecat.services.cartesia.tts import CartesiaTTSService
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.openai.llm import OpenAILLMService

    for key in ("DEEPGRAM_API_KEY", "OPENAI_API_KEY", "CARTESIA_API_KEY"):
        monkeypatch.setenv(key, "test-placeholder-not-a-real-key")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("TTS_PROVIDER", "cartesia")

    def reject_network(*args, **kwargs):
        pytest.fail("Provider construction must not open a network connection")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    stt, llm, tts = bot.build_services(load_config())
    assert isinstance(stt, DeepgramSTTService)
    assert isinstance(llm, OpenAILLMService)
    assert isinstance(tts, CartesiaTTSService)
    for service in (stt, llm, tts):
        await service.cleanup()


class EventSource:
    def __init__(self):
        self.handlers = {}

    def event_handler(self, name):
        def register(handler):
            self.handlers[name] = handler
            return handler

        return register


class FakeTransport(EventSource):
    def input(self):
        return "transport-input"

    def output(self):
        return "transport-output"


class FakeLLM:
    def __init__(self):
        self.functions = {}
        self.frames = []

    def register_function(self, name, handler):
        self.functions[name] = handler

    async def push_frame(self, frame):
        self.frames.append(frame)


@pytest.fixture
def session(monkeypatch):
    import pipecat.audio.vad.silero as vad_module
    import pipecat.pipeline.pipeline as pipeline_module
    import pipecat.pipeline.worker as worker_module
    import pipecat.processors.aggregators.llm_response_universal as aggregator_module
    import pipecat.workers.runner as runner_module

    fixture = SimpleNamespace(
        transport=FakeTransport(),
        llm=FakeLLM(),
        runner=None,
        worker=None,
        behavior=AsyncMock(),
        notify=AsyncMock(return_value={"sms": "skipped", "email": "skipped"}),
        args=SimpleNamespace(
            pipeline_idle_timeout_secs=60, handle_sigint=False, handle_sigterm=False
        ),
    )

    class FakePipeline:
        def __init__(self, processors):
            self.processors = processors

    class FakeWorker(EventSource):
        def __init__(self, pipeline, **kwargs):
            super().__init__()
            self.pipeline = pipeline
            self.queued = []
            fixture.worker = self

        async def queue_frame(self, frame):
            self.queued.append(frame)

    class FakeRunner:
        def __init__(self, **kwargs):
            self.cancel_reasons = []
            self.workers = []
            fixture.runner = self

        async def add_workers(self, worker):
            self.workers.append(worker)

        async def run(self):
            await fixture.behavior()

        async def cancel(self, reason=None):
            self.cancel_reasons.append(reason)

    monkeypatch.setattr(vad_module, "SileroVADAnalyzer", lambda: None)
    monkeypatch.setattr(
        aggregator_module, "LLMContextAggregatorPair", lambda *args, **kwargs: ("user", "assistant")
    )
    monkeypatch.setattr(pipeline_module, "Pipeline", FakePipeline)
    monkeypatch.setattr(worker_module, "PipelineWorker", FakeWorker)
    monkeypatch.setattr(runner_module, "WorkerRunner", FakeRunner)
    monkeypatch.setattr(bot, "build_services", lambda config: ("stt", fixture.llm, "tts"))
    monkeypatch.setattr(bot, "send_summary", fixture.notify)
    monkeypatch.setattr(bot, "max_call_seconds", lambda: 600)
    monkeypatch.setattr(
        bot,
        "ClinicTools",
        lambda config, store, call_id: ClinicTools(
            config, store, call_id, now=lambda: datetime(2027, 1, 4, 13, tzinfo=UTC)
        ),
    )

    async def call_tool(name, arguments):
        from pipecat.services.llm_service import FunctionCallParams

        callback = AsyncMock()
        await fixture.llm.functions[name](
            FunctionCallParams(
                function_name=name,
                tool_call_id=f"test-{name}",
                arguments=arguments,
                llm=fixture.llm,
                pipeline_worker=fixture.worker,
                context=None,
                result_callback=callback,
            )
        )
        callback.assert_awaited_once()
        return callback.await_args.args[0], callback.await_args.kwargs["properties"]

    fixture.call_tool = call_tool
    return fixture


async def test_tools_goodbye_and_final_summary_use_one_server_owned_call(session):
    from pipecat.frames.frames import EndWorkerFrame, TTSSpeakFrame

    async def conversation():
        await session.transport.handlers["on_client_connected"](session.transport, "demo-client")
        assert "AI receptionist" in session.worker.queued[0].text
        assert set(session.llm.functions) == {
            "get_hours",
            "list_services",
            "book_appointment",
            "take_message",
            "end_call",
        }
        hours, properties = await session.call_tool("get_hours", {"day": "monday"})
        assert hours["hours"]["monday"]["open"] == "09:00"
        # Leave normal inference scheduling to Pipecat so sibling tool calls
        # complete before the assistant responds.
        assert properties.run_llm is None
        request = {
            "patient_name": "Demo Patient",
            "phone": "+14155550100",
            "service_id": "cleaning",
            "appointment_date": "2027-01-04",
            "appointment_time": "10:00",
            "confirmed": True,
        }
        booking, _ = await session.call_tool("book_appointment", request)
        assert booking["status"] == "pending_confirmation"
        assert booking["appointment"]["call_id"]
        ended, properties = await session.call_tool("end_call", {"reason": "Caller finished"})
        assert ended["should_end"] is True
        assert properties.run_llm is False
        assert len(session.llm.frames) == 2
        assert isinstance(session.llm.frames[0], TTSSpeakFrame)
        assert session.llm.frames[0].interruptible is False
        assert "Goodbye" in session.llm.frames[0].text
        assert isinstance(session.llm.frames[1], EndWorkerFrame)
        # A repeated tool result or transport-close event must not duplicate the
        # goodbye or turn a completed conversation into a disconnected call.
        await session.call_tool("end_call", {})
        assert len(session.llm.frames) == 2
        await session.transport.handlers["on_client_disconnected"](session.transport, "demo-client")

    session.behavior = conversation
    with Store(":memory:") as store:
        await bot.run_session(session.transport, session.args, load_config(), store)
        session.notify.assert_awaited_once()
        summary, clinic_name = session.notify.await_args.args
        assert clinic_name == load_config().name
        assert summary["call"]["status"] == "completed"
        assert summary["call"]["end_reason"] == "Caller finished"
        assert summary["call"]["ended_at"]
        assert len(summary["appointments"]) == 1
        assert summary == store.get_call_summary(summary["call"]["call_id"])


@pytest.mark.parametrize(
    ("event", "status", "reason"),
    [
        ("disconnect", "disconnected", None),
        ("provider_error", "error", "voice_service_error"),
        ("idle", "timeout", "idle_timeout"),
    ],
)
async def test_transport_events_finalize_and_notify(session, event, status, reason):
    async def lifecycle():
        if event == "disconnect":
            await session.transport.handlers["on_client_disconnected"](session.transport, "client")
        elif event == "provider_error":
            await session.worker.handlers["on_pipeline_error"](session.worker, object())
        else:
            await session.worker.handlers["on_idle_timeout"](session.worker)

    session.behavior = lifecycle
    with Store(":memory:") as store:
        await bot.run_session(session.transport, session.args, load_config(), store)
        session.notify.assert_awaited_once()
        summary = session.notify.await_args.args[0]
        assert summary["call"]["status"] == status
        assert summary["call"]["end_reason"] == reason
        assert summary["call"]["ended_at"]
        assert session.runner.cancel_reasons


@pytest.mark.parametrize(
    ("exception", "status", "reason"),
    [
        (RuntimeError("simulated runner failure"), "error", "session_error"),
        (asyncio.CancelledError(), "disconnected", "session_cancelled"),
    ],
)
async def test_runner_failures_are_finalized_before_propagating(session, exception, status, reason):
    async def failure():
        raise exception

    session.behavior = failure
    with Store(":memory:") as store:
        with pytest.raises(type(exception)):
            await bot.run_session(session.transport, session.args, load_config(), store)
        session.notify.assert_awaited_once()
        summary = session.notify.await_args.args[0]
        assert summary["call"]["status"] == status
        assert summary["call"]["end_reason"] == reason
        assert summary["call"]["ended_at"]
        assert session.runner.cancel_reasons


async def test_service_constructor_failure_still_finalizes_call(session, monkeypatch):
    def fail_construction(config):
        raise ValueError("simulated configuration failure")

    monkeypatch.setattr(bot, "build_services", fail_construction)
    with Store(":memory:") as store:
        with pytest.raises(ValueError, match="simulated"):
            await bot.run_session(session.transport, session.args, load_config(), store)
        session.notify.assert_awaited_once()
        summary = session.notify.await_args.args[0]
        assert summary["call"]["status"] == "error"
        assert summary["call"]["ended_at"]
        assert summary["appointments"] == []
        assert session.runner is None
