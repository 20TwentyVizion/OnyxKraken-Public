"""OnyxKraken Face — animated face GUI with chat and voice integration."""


def __getattr__(name):
    """Lazy imports — avoid pulling heavy modules at package init time."""
    if name in ("FaceCanvas", "FaceApp", "Phoneme", "text_to_phonemes"):
        from face.face_gui import FaceCanvas, FaceApp, Phoneme, text_to_phonemes
        return {"FaceCanvas": FaceCanvas, "FaceApp": FaceApp,
                "Phoneme": Phoneme, "text_to_phonemes": text_to_phonemes}[name]
    if name == "OnyxKrakenApp":
        from face.app import OnyxKrakenApp
        return OnyxKrakenApp
    raise AttributeError(f"module 'face' has no attribute {name!r}")
