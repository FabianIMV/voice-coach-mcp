import pytest
import soundfile as sf

from tests import falso_sounddevice
from voice_coach_mcp.audio.grabacion import grabar, nombre_archivo
from voice_coach_mcp.errores import ErrorUsuario


def test_graba_y_remuestrea_a_16k(config, monkeypatch):
    llamadas = falso_sounddevice.instalar(monkeypatch, samplerate=48_000)
    r = grabar(2.0, "prueba", config)
    assert llamadas["samplerate"] == 48_000 and llamadas["frames"] == 96_000
    info = sf.info(r["audio"])
    assert (info.samplerate, info.channels) == (16_000, 1)
    assert info.duration == pytest.approx(2.0, abs=0.01)
    assert r["audio"].endswith("grabaciones/prueba.wav")
    assert r["advertencias"] == []
    assert r["confianza"]["nivel"] == "alta"
    assert r["niveles"]["pico_dbfs"] == pytest.approx(-10.5, abs=0.5)


def test_silencio_digital_avisa_permiso_microfono(config, monkeypatch):
    falso_sounddevice.instalar(monkeypatch, modo="silencio")
    r = grabar(1.0, None, config)
    codigos = [a["codigo"] for a in r["advertencias"]]
    assert codigos[0] == "sin_permiso_microfono"
    assert "Privacidad y seguridad" in r["advertencias"][0]["detalle"]
    assert r["confianza"]["valor"] == 0


def test_error_de_portaudio_es_error_legible(config, monkeypatch):
    falso_sounddevice.instalar(monkeypatch, modo="error")
    with pytest.raises(ErrorUsuario, match="Micrófono"):
        grabar(1.0, None, config)


@pytest.mark.parametrize("segundos", [0, -1, 500])
def test_valida_duracion(config, monkeypatch, segundos):
    falso_sounddevice.instalar(monkeypatch)
    with pytest.raises(ErrorUsuario, match="segundos"):
        grabar(segundos, None, config)


def test_nombre_archivo_sanitiza_y_no_sobrescribe(tmp_path):
    assert nombre_archivo("../mi toma:1.wav", tmp_path).name == "mi_toma_1.wav"
    (tmp_path / "toma.wav").touch()
    (tmp_path / "toma-2.wav").touch()
    assert nombre_archivo("toma", tmp_path).name == "toma-3.wav"
    assert nombre_archivo("canción", tmp_path).name == "canción.wav"
    assert nombre_archivo(None, tmp_path).name.startswith("grabacion-")
