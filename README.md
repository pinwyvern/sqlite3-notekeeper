### setup
create `archive/` and `inbox/`, store these side-by-side the scripts  
`process.py` -> takes notes from `inbox/` and sorts them into `archive/` in a `YYYY-MM-DD_HASH.txt` format  
`notes_db.py` -> used to build / query the sqlite3 database built out of the notes found in `archive/`  


### using notes_db.py
```
usage: notes_db.py [-h] [--db DB] {index,show,search,list} ...

Index and search a directory of text notes.

positional arguments:
  {index,show,search,list}
    index               Index or update notes
    show                Display a note by ID
    search              Search note contents
    list                List indexed notes

options:
  -h, --help            show this help message and exit
  --db DB               Database file (default: notes.db)
```
