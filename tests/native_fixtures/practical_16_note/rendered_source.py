import flpianoroll as flp

NOTES = [[60,1536,12,850394],[60,1680,12,551181],[60,1728,12,795276],[60,1872,12,598425],[60,1920,12,866142],[60,1992,12,488189],[60,2112,12,811024],[60,2232,12,566929],[60,2304,12,850394],[60,2448,12,551181],[60,2496,12,795276],[60,2568,12,519685],[60,2688,12,866142],[60,2856,12,503937],[60,2880,12,811024],[60,3024,12,629921]]

def createDialog() -> flp.ScriptDialog:
    return flp.ScriptDialog("DAWLoop Native Add", "Experimental add-only preview.")

def apply(form: flp.ScriptDialog) -> None:
    for number, tick, length, velocity in NOTES:
        note = flp.Note()
        note.number = number
        note.time = tick
        note.length = length
        note.velocity = velocity / 1000000
        flp.score.addNote(note)
