"""Errores que se muestran tal cual al usuario (y a Claude) como resultado de la tool."""


class ErrorUsuario(Exception):
    """Error esperable: archivo inexistente, parámetro inválido, falta un extra, etc."""
