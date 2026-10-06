import flpianoroll as flp

def createDialog() -> flp.ScriptDialog:
    return flp.ScriptDialog(
        "DAWLoop Target Probe",
        "Adds one disposable marker note."
    )

def apply(form: flp.ScriptDialog) -> None:
    note = flp.Note()
    note.number = 120
    note.time = 0
    note.length = flp.score.PPQ
    note.velocity = 0.5
    flp.score.addNote(note)
