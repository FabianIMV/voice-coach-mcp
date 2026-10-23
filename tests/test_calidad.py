import numpy as np

from tests import sintetico as s
from voice_coach_mcp.audio.calidad import evaluar, nivel_confianza


def _codigos(calidad):
    return {a["codigo"] for a in calidad.advertencias}


def test_audio_limpio_sin_advertencias():
    c = evaluar(s.secuencia([(60, 0.8), (64, 0.8)]))
    assert _codigos(c) == set()
    assert c.factor == 1.0
    assert c.snr_db is not None and c.snr_db > 40


def test_clipping():
    y = np.clip(s.secuencia([(60, 1.0)]) * 6, -1, 1)
    c = evaluar(y)
    assert "clipping" in _codigos(c)
    assert c.factor < 1


def test_ruido_de_fondo():
    c = evaluar(s.con_ruido(s.secuencia([(60, 0.8), (64, 0.8)], pausa=0.3), snr_db=6))
    assert "ruido" in _codigos(c)
    assert c.snr_db < 15


def test_nota_continua_sin_pausas_no_se_marca_como_ruido():
    c = evaluar(s.tono(60, 3.0))
    assert "ruido" not in _codigos(c)


def test_audio_corto():
    assert "audio_corto" in _codigos(evaluar(s.tono(60, 0.5), duracion_minima=1.0))


def test_silencio_digital_y_silencio():
    assert "silencio_digital" in _codigos(evaluar(np.zeros(16000, dtype=np.float32)))
    c = evaluar(s.tono(60, 1.0, amplitud=1e-4))
    assert "silencio" in _codigos(c)
    assert c.factor == 0


def test_nivel_confianza():
    assert nivel_confianza(0.9) == {"valor": 0.9, "nivel": "alta"}
    assert nivel_confianza(0.5)["nivel"] == "media"
    assert nivel_confianza(1.7)["valor"] == 1.0
