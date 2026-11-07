"""English / Greek text.

The code is written in English; tr() looks the text up in GREEK while the
language is Greek and falls back to the English when there's no entry, so
untranslated text (several exercise names) simply stays English.  Text with
values in it is translated as the template and formatted afterwards:
tr("Saved {}").format(name).

No pygame or OpenGL here.
"""

import unicodedata

LANGUAGES = ("el", "en")
language = "el"  # the app starts in Greek


def tr(text: str) -> str:
    return GREEK.get(text, text) if language == "el" else text


def variants(text):
    """The text in every language (for sizing and searching)."""
    return {text, GREEK.get(text, text)}


def upper(text):
    """Capitals without accents, as Greek writes them (ΑΣΚΗΣΕΙΣ, not ΑΣΚΉΣΕΙΣ)."""
    text = unicodedata.normalize("NFD", text.upper()).replace("́", "")
    return unicodedata.normalize("NFC", text)


def fold(text):
    """Lower case without accents, for searching: 'Προβολές' -> 'προβολεσ'."""
    text = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


# Joint and bone names, as skeleton.pretty_name writes them.  Sided names get
# the adjective in the noun's gender (masculine, feminine, neuter, plural).
_SIDES = {"left": ("αριστερός", "αριστερή", "αριστερό", "αριστερά"),
          "right": ("δεξιός", "δεξιά", "δεξί", "δεξιά")}
_SIDED = {
    "shoulder": ("ώμος", 0), "elbow": ("αγκώνας", 0), "hand": ("χέρι", 2), "hip": ("ισχίο", 2),
    "knee": ("γόνατο", 2), "eye": ("μάτι", 2),"ankle": ("αστράγαλος", 0), "toe": ("δάχτυλα ποδιού", 3),
    "collarbone": ("κλείδα", 1), "upper arm": ("βραχίονας", 0), "forearm": ("πήχης", 0),
    "hip bone": ("οστό ισχίου", 2), "thigh": ("μηρός", 0), "shin": ("κνήμη", 1), "foot": ("πέλμα", 2),
}
_PARTS = {
    "pelvis": "λεκάνη", "chest": "στήθος", "neck": "αυχένας", "head": "κεφάλι",
    "lower spine": "κάτω μέρος σπονδυλικής στήλης", "upper spine": "πάνω μέρος σπονδυλικής στήλης",
    "Nose": "Μύτη", "Tattoo": "Τατουάζ","Figure {}: ": "Φιγούρα {}: ",
    # equipment (props.py part names)
    "Bar": "Μπάρα", "Plate": "Δίσκος", "Dumbbell": "Αλτήρας", "Kettlebell": "Κέτλμπελ", "Post": "Ορθοστάτης",
    "Cable": "Συρματόσχοινο", "Handle": "Λαβή", "Bench": "Πάγκος", "Box": "Κουτί", "Wall": "Τοίχος",
    "Seat": "Κάθισμα", "Backrest": "Πλάτη καθίσματος",
}
_PARTS.update({f"{side} {part}": f"{forms[gender]} {noun}"
               for side, forms in _SIDES.items() for part, (noun, gender) in _SIDED.items()})

_UI = {
    # toolbar tooltips
    "Open a pose (Ctrl+O)": "Άνοιγμα πόζας (Ctrl+O)",
    "Save the pose (Ctrl+S)": "Αποθήκευση πόζας (Ctrl+S)",
    "Export a PNG image (Ctrl+E)": "Εξαγωγή εικόνας PNG (Ctrl+E)",
    "Copy as editable shapes for Word or PowerPoint (Ctrl+C)":
        "Αντιγραφή ως επεξεργάσιμα σχήματα για Word ή PowerPoint (Ctrl+C)",
    "Copy as a 3D model for Word or PowerPoint (Ctrl+Shift+C)":
        "Αντιγραφή ως τρισδιάστατο μοντέλο για Word ή PowerPoint (Ctrl+Shift+C)",
    "Export a 3D model file, .glb (Ctrl+Shift+E)": "Εξαγωγή αρχείου τρισδιάστατου μοντέλου, .glb (Ctrl+Shift+E)",
    "Undo (Ctrl+Z)": "Αναίρεση (Ctrl+Z)",
    "Redo (Ctrl+Y)": "Επανάληψη (Ctrl+Y)",
    "Reset the pose (R)": "Επαναφορά πόζας (R)",
    "Put the figure on the floor (G)": "Τοποθέτηση της φιγούρας στο δάπεδο (G)",
    "Realistic joint limits on / off (L)": "Ρεαλιστικά όρια αρθρώσεων: ενεργοποίηση / απενεργοποίηση (L)",
    "Drag joints parallel to the screen": "Σύρσιμο αρθρώσεων παράλληλα με την οθόνη",
    "Drag joints parallel to the floor (or hold Ctrl while dragging)":
        "Σύρσιμο αρθρώσεων παράλληλα με το δάπεδο (ή κρατήστε πατημένο το Ctrl κατά το σύρσιμο)",
    "Drag joints straight up / down (or hold Shift while dragging)":
        "Σύρσιμο αρθρώσεων κατακόρυφα πάνω / κάτω (ή κρατήστε πατημένο το Shift κατά το σύρσιμο)",
    "Pin / unpin the selected joint (P)": "Καρφίτσωμα / ξεκαρφίτσωμα της επιλεγμένης άρθρωσης (P)",
    "Unpin all joints (Shift+P)": "Ξεκαρφίτσωμα όλων των αρθρώσεων (Shift+P)",
    "Copy the selected side onto the other side (M)": "Αντιγραφή της επιλεγμένης πλευράς στην άλλη πλευρά (M)",
    "Twist the selected joint one way (Z, Shift-click: 5 deg)":
        "Περιστροφή της επιλεγμένης άρθρωσης προς τη μία φορά (Z, Shift+κλικ: 5°)",
    "Twist the selected joint the other way (X, Shift-click: 5 deg)":
        "Περιστροφή της επιλεγμένης άρθρωσης προς την άλλη φορά (X, Shift+κλικ: 5°)",
    "Raise the figure (Up arrow, Shift-click: 1 cm)": "Ανύψωση της φιγούρας (πάνω βέλος, Shift+κλικ: 1 cm)",
    "Lower the figure (Down arrow, Shift-click: 1 cm)": "Χαμήλωμα της φιγούρας (κάτω βέλος, Shift+κλικ: 1 cm)",
    "Turn the figure to its left (Q, Shift-click: 5 deg)": "Στροφή της φιγούρας προς τα αριστερά της (Q, Shift+κλικ: 5°)",
    "Turn the figure to its right (E, Shift-click: 5 deg)": "Στροφή της φιγούρας προς τα δεξιά της (E, Shift+κλικ: 5°)",
    "Tip the figure forward (W, Shift-click: 5 deg)": "Κλίση της φιγούρας προς τα εμπρός (W, Shift+κλικ: 5°)",
    "Tip the figure back (S, Shift-click: 5 deg)": "Κλίση της φιγούρας προς τα πίσω (S, Shift+κλικ: 5°)",
    "Lean the figure to its left (A, Shift-click: 5 deg)":
        "Πλάγια κλίση της φιγούρας προς τα αριστερά της (A, Shift+κλικ: 5°)",
    "Lean the figure to its right (D, Shift-click: 5 deg)":
        "Πλάγια κλίση της φιγούρας προς τα δεξιά της (D, Shift+κλικ: 5°)",
    "Front view (1)": "Πρόσοψη (1)",
    "Side view (2)": "Πλάγια όψη (2)",
    "Top view (3)": "Κάτοψη (3)",
    "Angled view (4)": "Όψη υπό γωνία (4)",
    "Centre the view on the figure (F)": "Κεντράρισμα της προβολής στη φιγούρα (F)",
    "Zoom in (+ or mouse wheel)": "Μεγέθυνση (+ ή ροδέλα ποντικιού)",
    "Zoom out (- or mouse wheel)": "Σμίκρυνση (- ή ροδέλα ποντικιού)",
    "Show / hide the help (H)": "Εμφάνιση / απόκρυψη βοήθειας (H)",
    "Language: English. Switch to Greek (T)": "Γλώσσα: Ελληνικά. Αλλαγή σε αγγλικά (T)",
    "About Stickman (I)": "Σχετικά με το Stickman (I)",
    "Instructions": "Οδηγίες",
    # the info text (scene.ABOUT)
    "Quickly and easily create exercise illustrations by posing a 3D stick figure in different positions.":
        "Δημιουργήστε εύκολα και γρήγορα σκίτσα ασκήσεων τοποθετώντας ένα τρισδιάστατο ανθρωπάκι σε διάφορες "
        "στάσεις.",
    "Inspired by the simple stick-figure sketches my coach used to draw to illustrate exercises, I created "
    "Stickman with the help of Artificial Intelligence (AI). The application allows users to pose a 3D stick "
    "figure in different positions, making it quick and easy to create exercise illustrations for workout "
    "programmes. It is available both as a desktop application and through a website.":
        "Εμπνευσμένος από τα απλά σκίτσα με ανθρωπάκια που σχεδίαζε ο προπονητής μου για να απεικονίζει "
        "ασκήσεις, δημιούργησα με τη βοήθεια της Τεχνητής Νοημοσύνης το Stickman. Η εφαρμογή επιτρέπει την "
        "τοποθέτηση ενός τρισδιάστατου ανθρώπινου μοντέλου σε διάφορες στάσεις, διευκολύνοντας τη γρήγορη "
        "δημιουργία σκίτσων ασκήσεων για προγράμματα προπόνησης. Διατίθεται τόσο ως εφαρμογή για υπολογιστές "
        "όσο και μέσω ιστοσελίδας.",
    # exercise list
    "Choose an exercise (Tab)": "Επιλογή άσκησης (Tab)",
    "2 positions": "2 θέσεις",
    "Type to search...": "Πληκτρολογήστε για αναζήτηση...",
    "No exercise matches": "Δεν βρέθηκε άσκηση",
    # messages and status line
    "Language: English": "Γλώσσα: Ελληνικά",
    "{}: start position on the left, end position on the right": "{}: αρχική θέση αριστερά, τελική θέση δεξιά",
    "All pins removed": "Αφαιρέθηκαν όλες οι καρφίτσες",
    "Click a joint first, then press P to pin it":
        "Κάντε πρώτα κλικ σε μια άρθρωση και μετά πατήστε P για να την καρφιτσώσετε",
    "Select a left or right joint to mirror its side":
        "Επιλέξτε μια αριστερή ή δεξιά άρθρωση για να αντιγράψετε την πλευρά της στην άλλη",
    "Copied left side onto the other side": "Η αριστερή πλευρά αντιγράφηκε στην άλλη πλευρά",
    "Copied right side onto the other side": "Η δεξιά πλευρά αντιγράφηκε στην άλλη πλευρά",
    "Click a joint first, then press Z/X to twist it":
        "Κάντε πρώτα κλικ σε μια άρθρωση και μετά πατήστε Z/X για να την περιστρέψετε",
    "This joint can't twist any further": "Αυτή η άρθρωση δεν περιστρέφεται άλλο",
    "Joint limits on": "Όρια αρθρώσεων ενεργά",
    "Joint limits OFF": "Όρια αρθρώσεων ΑΝΕΝΕΡΓΑ",
    "Pose reset (Ctrl+Z to undo)": "Επαναφορά πόζας (Ctrl+Z για αναίρεση)",
    "Saved {}": "Αποθηκεύτηκε: {}",
    "Opened {}": "Άνοιξε: {}",
    "Exported {}": "Η εξαγωγή ολοκληρώθηκε: {}",
    "Could not open pose: {}": "Δεν ήταν δυνατό το άνοιγμα της πόζας: {}",
    "Could not copy: {}": "Δεν ήταν δυνατή η αντιγραφή: {}",
    "Copied figure: paste into Word or PowerPoint": "Η φιγούρα αντιγράφηκε: επικολλήστε τη στο Word ή στο PowerPoint",
    "Copied figure as a 3D model: paste into Word or PowerPoint":
        "Η φιγούρα αντιγράφηκε ως τρισδιάστατο μοντέλο: επικολλήστε τη στο Word ή στο PowerPoint",
    "Selected: {}": "Επιλογή: {}",
    " (pinned)": " (με καρφίτσα)",
    " of figure {}": " της φιγούρας {}",
    "Pins: {}": "Καρφίτσες: {}",
    # file dialogs
    "Save pose": "Αποθήκευση πόζας",
    "Open pose": "Άνοιγμα πόζας",
    "Export image": "Εξαγωγή εικόνας",
    "Export 3D model": "Εξαγωγή τρισδιάστατου μοντέλου",
    "Pose": "Πόζα",
    "PNG image": "Εικόνα PNG",
    "3D model (glTF)": "Τρισδιάστατο μοντέλο (glTF)",
    "All files": "Όλα τα αρχεία",
    # the website (web/)
    "Copy as a picture for Word or PowerPoint (Ctrl+C)": "Αντιγραφή ως εικόνα για Word ή PowerPoint (Ctrl+C)",
    "Download as editable shapes for PowerPoint or Word, .pptx (Ctrl+Shift+S)":
        "Λήψη ως επεξεργάσιμα σχήματα για PowerPoint ή Word, .pptx (Ctrl+Shift+S)",
    "Copied figure: paste into Word or PowerPoint (right-click > Convert to Shape to edit it)":
        "Η φιγούρα αντιγράφηκε: επικολλήστε τη στο Word ή στο PowerPoint"
        " (δεξί κλικ > Μετατροπή σε σχήμα για επεξεργασία)",
    "Copied figure as an image: paste into Word or PowerPoint":
        "Η φιγούρα αντιγράφηκε ως εικόνα: επικολλήστε τη στο Word ή στο PowerPoint",
    "Browsers can't copy 3D models: export one (Ctrl+Shift+E), then use Insert > 3D Models in Office":
        "Τα προγράμματα περιήγησης δεν αντιγράφουν τρισδιάστατα μοντέλα: κάντε εξαγωγή (Ctrl+Shift+E)"
        " και μετά Εισαγωγή > Τρισδιάστατα μοντέλα στο Office",
    "Copying needs a secure page (https)": "Η αντιγραφή χρειάζεται ασφαλή σελίδα (https)",
}

# Exercise categories and names (exercises.CATEGORIES).  Names without an
# established Greek term are left out and stay English.
_EXERCISES = {
    "Basic positions": "Βασικές θέσεις",
    "Standing": "Όρθια στάση",
    "Standing, arms out (T-pose)": "Όρθια στάση, χέρια ανοιχτά (T-pose)",
    "Walking": "Περπάτημα",
    "Running": "Τρέξιμο",
    "Sitting on a chair": "Καθιστή θέση σε καρέκλα",
    "Sitting on the floor": "Καθιστή θέση στο πάτωμα",
    "Kneeling": "Γονατιστή θέση",
    "Half kneeling": "Γονατιστή θέση στο ένα γόνατο",
    "Deep squat (resting)": "Βαθύ κάθισμα (ανάπαυση)",
    "Lying on the back": "Ύπτια κατάκλιση (ανάσκελα)",
    "Lying face down": "Πρηνής κατάκλιση (μπρούμυτα)",
    "Lying on the side": "Πλάγια κατάκλιση",

    "Legs and glutes": "Πόδια και γλουτοί",
    "Squat": "Καθίσματα",
    "Half squat": "Ημικαθίσματα",
    "Back squat": "Οπίσθια καθίσματα",
    "Front squat": "Εμπρόσθια καθίσματα",
    "Lunge": "Προβολές",
    "Side lunge": "Πλάγιες προβολές",
    "Calf raise": "Ανυψώσεις στις μύτες των ποδιών",
    "Glute bridge": "Γέφυρα γλουτών",
    "Single-leg glute bridge": "Γέφυρα γλουτών με το ένα πόδι",
    "Deadlift": "Άρση θανάτου",
    "Romanian deadlift": "Ρουμανική άρση θανάτου",
    "Single-leg Romanian deadlift": "Ρουμανική άρση θανάτου με το ένα πόδι",
    "Side-lying leg raise": "Ανυψώσεις ποδιού σε πλάγια κατάκλιση",
    "Standing side leg raise": "Πλάγιες ανυψώσεις ποδιού από όρθια θέση",
    "Standing hip extension": "Εκτάσεις ισχίου από όρθια θέση",

    "Push": "Ασκήσεις ώθησης",
    "Push-up": "Κάμψεις",
    "Knee push-up": "Κάμψεις στα γόνατα",
    "Wide push-up": "Κάμψεις με ανοιχτά χέρια",
    "Diamond push-up": "Κάμψεις διαμάντι",
    "Incline push-up": "Κάμψεις με τα χέρια ψηλότερα",
    "Decline push-up": "Κάμψεις με τα πόδια ψηλότερα",
    "Handstand": "Κατακόρυφο",
    "Dip": "Βυθίσεις",
    "Bench dip": "Βυθίσεις σε πάγκο",
    "Bench press": "Πιέσεις πάγκου",
    "Floor press": "Πιέσεις στήθους στο πάτωμα",
    "Dumbbell fly": "Ανοίγματα με αλτήρες",
    "Overhead press": "Πιέσεις ώμων",
    "Overhead triceps extension": "Εκτάσεις τρικεφάλων πάνω από το κεφάλι",

    "Pull": "Ασκήσεις έλξης",
    "Pull-up": "Έλξεις",
    "Chin-up": "Έλξεις με ύπτια λαβή",
    "Hanging leg raise": "Ανυψώσεις ποδιών σε κρέμαση",
    "Hanging knee raise": "Ανυψώσεις γονάτων σε κρέμαση",
    "Dead hang": "Κρέμαση από μονόζυγο",
    "Bent-over row": "Κωπηλατική με σκυμμένο κορμό",
    "One-arm row": "Κωπηλατική με ένα χέρι",
    "Lat pulldown": "Έλξεις στην τροχαλία",
    "Seated row": "Καθιστή κωπηλατική",
    "Rear delt fly": "Ανοίγματα για οπίσθιους δελτοειδείς",

    "Arms and shoulders": "Χέρια και ώμοι",
    "Biceps curl": "Κάμψεις δικεφάλων",
    "Lateral raise": "Πλάγιες ανυψώσεις",
    "Front raise": "Εμπρόσθιες ανυψώσεις",
    "Upright row": "Όρθια κωπηλατική",
    "Shrug": "Ανασηκώσεις ώμων",
    "Arm circles": "Κύκλοι χεριών",
    "Overhead carry": "Μεταφορά βάρους πάνω από το κεφάλι",

    "Core": "Κορμός",
    "Plank": "Σανίδα",
    "Forearm plank": "Σανίδα στους πήχεις",
    "Side plank": "Πλάγια σανίδα",
    "Side plank, arm raised": "Πλάγια σανίδα με σηκωμένο χέρι",
    "Sit-up": "Ανακάμψεις κορμού",
    "Leg raise": "Ανυψώσεις ποδιών",
    "Boat pose": "Στάση της βάρκας",
    "Standing torso twist": "Περιστροφές κορμού από όρθια θέση",

    "Cardio and plyometrics": "Αερόβιες και πλειομετρικές ασκήσεις",
    "Squat jump": "Άλματα από κάθισμα",
    "Tuck jump": "Άλματα με συσπείρωση",
    "High knees": "Ψηλά γόνατα",
    "Butt kicks": "Φτέρνες στους γλουτούς",
    "Jump rope": "Σχοινάκι",
    "Shadow boxing (jab, cross)": "Σκιαμαχία (jab, cross)",

    "Running drills": "Ασκήσεις τεχνικής τρεξίματος",
    "Running stride": "Διασκελισμός τρεξίματος",
    "Sprint start": "Χαμηλή εκκίνηση",
    "Leg swing, front to back": "Αιωρήσεις ποδιού, εμπρός-πίσω",
    "Leg swing, side to side": "Αιωρήσεις ποδιού, πλάγια",
    "Walking lunge": "Προβολές με βάδισμα",

    "Stretching": "Διατάσεις",
    "Standing quad stretch": "Διάταση τετρακεφάλων από όρθια θέση",
    "Standing hamstring stretch": "Διάταση οπίσθιων μηριαίων από όρθια θέση",
    "Seated forward fold": "Πρόσθια κάμψη κορμού από καθιστή θέση",
    "Butterfly stretch": "Διάταση πεταλούδα",
    "Hip flexor stretch": "Διάταση καμπτήρων ισχίου",
    "Calf stretch": "Διάταση γαστροκνημίων",
    "Side bend stretch": "Διάταση με πλάγια κάμψη κορμού",
    "Overhead triceps stretch": "Διάταση τρικεφάλων πάνω από το κεφάλι",
    "Cross-body shoulder stretch": "Διάταση ώμου, χέρι μπροστά από το στήθος",
    "Chest stretch": "Διάταση στήθους",
    "Neck stretch": "Διάταση αυχένα",
    "Knee to chest": "Γόνατο στο στήθος",
    "Lying spinal twist": "Περιστροφή κορμού από ύπτια θέση",
    "Child's pose": "Στάση του παιδιού",
    "Cobra": "Κόμπρα",
    "Cat-cow": "Γάτα-αγελάδα",
    "Arm and shoulder circles": "Κύκλοι χεριών και ώμων",

    "Yoga": "Γιόγκα",
    "Mountain pose": "Στάση του βουνού",
    "Downward dog": "Σκύλος με το κεφάλι κάτω",
    "Upward dog": "Σκύλος με το κεφάλι πάνω",
    "Plank pose": "Στάση σανίδας",
    "Chair pose": "Στάση της καρέκλας",
    "Warrior I": "Πολεμιστής I",
    "Warrior II": "Πολεμιστής II",
    "Warrior III": "Πολεμιστής III",
    "Tree pose": "Στάση του δέντρου",
    "Triangle pose": "Στάση του τριγώνου",
    "Bridge pose": "Στάση της γέφυρας",
    "Happy baby": "Χαρούμενο μωρό",
    "Corpse pose": "Στάση του πτώματος",
}

GREEK = {**_PARTS, **_UI, **_EXERCISES}
