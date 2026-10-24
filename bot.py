"""Pipecat 1.14 voice receptionist. Run `python bot.py` for the browser demo."""

import asyncio
import logging
import sys
from contextlib import suppress

from dotenv import load_dotenv

from config import ClinicConfig, load_config
from notify import send_summary
from settings import ROOT, env_value, local_path, max_call_seconds, require_voice_settings
from store import Store
from tools import TOOL_SCHEMAS, ClinicTools

# Do not override credentials set by the hosting environment.
load_dotenv(ROOT / ".env")


def configure_logging() -> None:
    # Pipecat debug logs can include transcripts. Keep these off for the demo.
    from loguru import logger

    level = env_value("LOG_LEVEL", "WARNING").upper()
    logger.remove()
    logger.add(sys.stderr, level=level)
    logging.basicConfig(level=level)


def build_services(config: ClinicConfig):
    """Construct the current service APIs without opening provider connections."""
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.openai.llm import OpenAILLMService

    require_voice_settings()
    stt = DeepgramSTTService(
        api_key=env_value("DEEPGRAM_API_KEY"),
        settings=DeepgramSTTService.Settings(model=env_value("DEEPGRAM_MODEL", "nova-3-general")),
    )
    llm = OpenAILLMService(
        api_key=env_value("OPENAI_API_KEY"),
        settings=OpenAILLMService.Settings(
            model=env_value("OPENAI_MODEL", "gpt-4o-mini"),
            system_instruction=config.system_prompt(),
        ),
    )
    if env_value("TTS_PROVIDER", "cartesia") == "elevenlabs":
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

        tts = ElevenLabsTTSService(
            api_key=env_value("ELEVENLABS_API_KEY"),
            settings=ElevenLabsTTSService.Settings(
                voice=env_value("ELEVENLABS_VOICE_ID"),
                model=env_value("ELEVENLABS_MODEL", "eleven_flash_v2_5"),
            ),
        )
    else:
        from pipecat.services.cartesia.tts import CartesiaTTSService

        tts = CartesiaTTSService(
            api_key=env_value("CARTESIA_API_KEY"),
            settings=CartesiaTTSService.Settings(
                voice=env_value("CARTESIA_VOICE_ID"),
                model=env_value("CARTESIA_MODEL", "sonic-3.6"),
            ),
        )
    return stt, llm, tts


def daily_params():
    # Daily is genuinely optional: browser and phone never import daily-python.
    from pipecat.transports.daily.transport import DailyParams

    return DailyParams(audio_in_enabled=True, audio_out_enabled=True)


async def run_session(transport, runner_args, config: ClinicConfig, store: Store) -> None:
    from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import (
        EndWorkerFrame,
        FunctionCallResultProperties,
        TTSSpeakFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
        LLMUserAggregatorParams,
    )
    from pipecat.services.llm_service import FunctionCallParams
    from pipecat.workers.runner import WorkerRunner

    call_duration = max_call_seconds()
    call = store.create_call()
    call_id = call["call_id"]  # Never use an LLM- or caller-supplied database identifier.
    status, reason = "completed", None
    ending = False
    runner = None
    deadline = None
    try:
        stt, llm, tts = build_services(config)
        clinic_tools = ClinicTools(config, store, call_id)

        async def handle_tool(params: FunctionCallParams):
            nonlocal ending, reason
            # The validated, transactional local operation finishes before an await.
            result = clinic_tools.dispatch(params.function_name, params.arguments)
            should_end = result.get("should_end", False)
            await params.result_callback(
                result,
                properties=FunctionCallResultProperties(run_llm=False if should_end else None),
            )
            if should_end and not ending:
                ending = True
                reason = result.get("reason", "caller_finished")
                goodbye = TTSSpeakFrame("Thank you for calling. Goodbye!")
                goodbye.interruptible = False
                await params.llm.push_frame(goodbye)
                # Graceful closure flushes synthesis and playback before hanging up.
                await params.llm.push_frame(EndWorkerFrame())

        schemas = []
        for item in TOOL_SCHEMAS:
            definition = item["function"]
            schemas.append(
                FunctionSchema(
                    name=definition["name"],
                    description=definition["description"],
                    properties=definition["parameters"]["properties"],
                    required=definition["parameters"].get("required", []),
                )
            )
            llm.register_function(definition["name"], handle_tool)

        context = LLMContext(tools=schemas)
        user, assistant = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
        )
        pipeline = Pipeline([transport.input(), stt, user, llm, tts, transport.output(), assistant])
        worker = PipelineWorker(
            pipeline,
            params=PipelineParams(audio_in_sample_rate=16000, audio_out_sample_rate=24000),
            idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
            processor_unusable_policy=ProcessorUnusablePolicy.END,
        )
        runner = WorkerRunner(
            handle_sigint=runner_args.handle_sigint,
            handle_sigterm=runner_args.handle_sigterm,
        )

        @transport.event_handler("on_client_connected")
        async def on_connected(_transport, _client):
            await worker.queue_frame(
                TTSSpeakFrame(
                    f"Thank you for calling {config.name}. I'm your AI receptionist. "
                    "I can help with clinic information, appointment requests, or a message. "
                    "How can I help?"
                )
            )

        @transport.event_handler("on_client_disconnected")
        async def on_disconnected(_transport, _client):
            nonlocal status
            if not ending and status == "completed":
                status = "disconnected"
            await runner.cancel()

        @worker.event_handler("on_pipeline_error")
        async def on_error(_worker, _frame):
            nonlocal status, reason
            status, reason = "error", "voice_service_error"
            # Do not persist or print provider errors, which may contain caller data.
            logging.getLogger(__name__).warning("Voice service reported an error")

        @worker.event_handler("on_idle_timeout")
        async def on_idle(_worker):
            nonlocal status, reason
            status, reason = "timeout", "idle_timeout"

        async def limit_duration():
            nonlocal status, reason
            await asyncio.sleep(call_duration)
            status, reason = "timeout", "maximum_duration"
            await runner.cancel(reason="maximum_duration")

        await runner.add_workers(worker)
        deadline = asyncio.create_task(limit_duration())
        await runner.run()
    except asyncio.CancelledError:
        status, reason = "disconnected", "session_cancelled"
        raise
    except Exception:
        status, reason = "error", "session_error"
        raise
    finally:
        if deadline:
            deadline.cancel()
            with suppress(asyncio.CancelledError):
                await deadline
        if runner:
            await runner.cancel()
        store.finish_call(call_id, status=status, reason=reason)
        await send_summary(store.get_call_summary(call_id), config.name)


async def bot(runner_args):
    """Pipecat development runner entry point, also used by server.py."""
    from pipecat.runner.utils import create_transport
    from pipecat.transports.base_transport import TransportParams
    from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams

    require_voice_settings()
    config = load_config(local_path("CLINIC_CONFIG_PATH", "clinic_config.yaml"))
    transport = await create_transport(
        runner_args,
        {
            "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
            "daily": daily_params,
            "twilio": lambda: FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True),
        },
    )
    with Store(local_path("DATABASE_PATH", "data/clinic.sqlite3")) as store:
        await run_session(transport, runner_args, config, store)


if __name__ == "__main__":
    configure_logging()
    # Runner 1.14 enables all transports by default. This demo explicitly defaults
    # to browser mode while retaining `-t daily` as an optional override.
    if not any(arg in {"-t", "--transport"} or arg.startswith("--transport=") for arg in sys.argv):
        sys.argv.extend(["-t", "webrtc"])
    if not any(arg in {"-h", "--help"} for arg in sys.argv):
        require_voice_settings()
        load_config(local_path("CLINIC_CONFIG_PATH", "clinic_config.yaml"))
        max_call_seconds()
    from pipecat.runner.run import main

    main()
