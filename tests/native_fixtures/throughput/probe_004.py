import flpianoroll as flp

NOTE_COUNT = 4

def createDialog() -> flp.ScriptDialog:
    return flp.ScriptDialog("DAWLoop Throughput Probe", "Adds a fixed disposable grid.")

def apply(form: flp.ScriptDialog) -> None:
    ppq = flp.score.PPQ
    for index in range(NOTE_COUNT):
        note = flp.Note()
        note.number = 84 + index // 16
        note.time = 32 * ppq + (index % 16) * (ppq // 2)
        note.length = ppq // 4
        note.velocity = 0.5
        flp.score.addNote(note)
