The Document Composer's caption font, Stickman Sans (Regular and Bold): Liberation Sans 2.1.5 by Red Hat,
licensed under the SIL Open Font License, Version 1.1 (OFL.txt). It has the same letter widths as Arial,
which the Word and PowerPoint exports name, so captions wrap the same everywhere.

The files are subsets, renamed because the licence reserves the name Liberation for the original fonts.
They keep Basic Latin, Latin-1, Latin Extended-A, Greek and some punctuation, and were made with:

    python -m fontTools.subset LiberationSans-Regular.ttf --unicodes="U+0020-007E,U+00A0-017F,U+0370-03FF,U+2010-2027,U+2030-203A,U+20AC,U+2122,U+2190-2193,U+2212,U+00B0" --layout-features="kern" --no-hinting --drop-tables+=GSUB,GPOS,GDEF,DSIG

(and the same for LiberationSans-Bold.ttf), then given the name Stickman Sans in their name tables.
