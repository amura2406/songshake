from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("song-shake")
except PackageNotFoundError:
    __version__ = "0.0.0"
