"""Interfaz común de los backends de pronunciación y su resultado normalizado."""

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from ..config import Config


@dataclass
class ErrorFonema:
    tipo: str  # "sustitucion" | "omision" | "insercion"
    esperado: str | None = None
    detectado: str | None = None

    def a_dict(self) -> dict:
        d = {"tipo": self.tipo}
        if self.esperado:
            d["esperado"] = self.esperado
        if self.detectado:
            d["detectado"] = self.detectado
        return d


@dataclass
class ResultadoPalabra:
    palabra: str
    puntaje: float  # 0–100
    esperados: list[str] = field(default_factory=list)
    detectados: list[str] = field(default_factory=list)
    errores: list[ErrorFonema] = field(default_factory=list)
    inicio: float | None = None
    omitida: bool = False  # la palabra entera no se dijo


@dataclass
class ResultadoPronunciacion:
    backend: str
    palabras: list[ResultadoPalabra]
    puntaje_global: float
    confianza_modelo: float  # 0–1, certeza del backend sobre lo que detectó
    distancia_relativa: float  # distancia de edición / fonemas esperados
    fonemas_esperados: list[str] = field(default_factory=list)
    fonemas_detectados: list[str] = field(default_factory=list)
    advertencias: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)  # métricas propias del backend


class BackendPronunciacion(Protocol):
    nombre: str

    def evaluar(
        self, y: np.ndarray, texto: str, idioma: str, config: Config
    ) -> ResultadoPronunciacion: ...
