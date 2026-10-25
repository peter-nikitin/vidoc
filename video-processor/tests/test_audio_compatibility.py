"""Проверка совместимости декодера на локальном PCM WAV без модели и сети."""

import wave

from faster_whisper.audio import decode_audio


def test_whisper_decodes_pcm_wav(tmp_path):
    wav = tmp_path / "speech.wav"
    with wave.open(str(wav), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x00" * 1600)

    audio = decode_audio(str(wav), sampling_rate=16000)

    assert audio.shape == (1600,)
    assert audio.dtype.name == "float32"
    assert not audio.any()
