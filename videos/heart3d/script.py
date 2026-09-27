"""Narration for the 3D heart video, one entry per shot.

Each shot lasts as long as its narration (plus ``hold`` seconds), so the
visuals in web/heart3d.js are written against the sentence start times
that build3d.py puts in timeline.json.
"""

TITLE = "The Heart in 3D"

SHOTS = [
    ("intro", 1.0, [
        "This is a real, three-dimensional model of a human heart, built from an open anatomical atlas.",
        "Let's explore how it works, from the outside in.",
    ]),
    ("exterior", 1.0, [
        "At the top are the great vessels.",
        "The aorta carries oxygen-rich blood out to the body.",
        "The pulmonary trunk carries oxygen-poor blood to the lungs.",
        "And the superior vena cava brings blood back from the upper body.",
        "The coronary arteries, shown in red, wrap around the surface to feed the heart muscle itself.",
    ]),
    ("xray", 1.0, [
        "Now let's make the muscle transparent.",
        "Inside are four chambers.",
        "On the heart's right side, the right atrium and right ventricle hold oxygen-poor blood.",
        "On its left side, the left atrium and left ventricle hold oxygen-rich blood.",
    ]),
    ("valves", 1.0, [
        "Four valves keep the blood moving in one direction.",
        "Seen from above, the tricuspid and mitral valves open into the ventricles.",
        "The pulmonary and aortic valves open into the great arteries.",
    ]),
    ("flow", 1.5, [
        "Now, follow the blood.",
        "Oxygen-poor blood from the body fills the right atrium, passes the tricuspid valve into the right ventricle, "
        "and is pumped through the pulmonary valve toward the lungs.",
        "Oxygen-rich blood returns from the lungs through the pulmonary veins into the left atrium, flows through the "
        "mitral valve into the left ventricle, and is pumped through the aortic valve into the aorta.",
    ]),
    ("beat", 4.0, [
        "With each beat, the atria contract first, topping up the ventricles.",
        "Then the ventricles contract, and the valves close in turn, making the familiar lub-dub sound.",
    ]),
    ("section", 1.5, [
        "Slicing through the heart reveals its walls.",
        "The left ventricle's wall is about ten millimetres thick, far thicker than the right's, "
        "because it must pump blood around the entire body.",
    ]),
    ("outro", 3.0, [
        "Everything in this video, from the anatomy model to the voice, is free and open source.",
    ]),
]
