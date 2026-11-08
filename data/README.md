# Demonstration data

`demo_source.csv` and `demo_warehouse.csv` are **original, small synthetic examples** created for this portfolio edition. They are not CTG's source or warehouse files and do not reproduce individual rows from the original exercise.

They intentionally demonstrate: a missing ID (`103`), an extra ID (`109`), a duplicated warehouse ID (`104`), a changed market value (`102`), an empty warehouse security name (`105`), a changed and provisionally unrecognized currency (`106`), a negative value copied unchanged on both sides (`107`), and numerical equivalence (`100.0` vs `100.00` at ID `101`).

To analyze another dataset, supply your own two CSV files with the seven documented columns using `--source` and `--warehouse`. Dataset-specific baseline verification is only enabled for recognized input hashes; the automated tests always run.
