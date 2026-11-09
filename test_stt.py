from screening_ai.stt_service import FasterWhisperProvider

stt = FasterWhisperProvider(model_size="small")

result = stt.transcribe(
    r"data\day24_stt_evaluation\audio\USA.wav",
    language="en"
)

print(result.to_dict())