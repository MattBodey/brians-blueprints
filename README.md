# Brian's Blueprints

Brian's Blueprints for Factorio

Don't just look at the latest release shown on the left. Each book is released separately so to see them you have to go to the [all-releases page](https://github.com/bcwhite-code/brians-blueprints/releases).

Blueprints include:

- [Brian's Bootstrap](./brians-bootstrap/)
- [Brian's Trains](./brians-trains/)
- [Brian's Trains Auxiliary](./brians-trains-auxiliary/)
- [Finite State Machine](./finite-state-machine/)
- [SBF Big Blocks](./sbf-big-blocks/)
- [Self Building Angel Bob](./self-building-angelbob/)
- [Self Building Factory](./self-building-factory/)
- [Self Building Rocket](./self-building-rocket/)
- [Self Building Space Exploration](./self-building-spacex/)
- [Tileable Reactor](./tileable-reactor/)

## Commands

You will need [fatul](https://github.com/nyurik/fatul) to encode/decode blueprints. It is included in [tools](./tools/) folder.

Replace `book-dir` with the blueprint directory you want to use.

### Preprocess Blueprints (Merge Headers)

Some blueprint directories contain `headers/` subdirectories with train system-specific configurations (LTN, Cybersyn, Vanilla). The `prebuild.py` script automatically merges these headers with body blueprints to generate system-specific variants.

```sh
tools/prebuild.py -v --clean brians-trains/book ./dist
```

This will:
- Process the source directory structure
- Find directories with `headers/` subdirectories
- Merge each header with all body blueprints in that directory
- Create organized output in `./dist/brians-trains/book/` with header-specific subdirectories
- Copy metadata and preserve directory structure

For example, if you want to build Brian's trains Blueprint book with all merged variants:

```sh
tools/prebuild.py -v --clean brians-trains/book ./dist
tools/fatul.py encode -v ./dist/brians-trains/book brians-train.txt
```

### Merge Blueprints Manually

To manually merge a header with a body blueprint:

```sh
tools/merge-blueprints.py body.json header.json -o merged.json -v
```

The merge uses train-stop entities as anchor points for precise alignment.

### Decode a Blueprint Book

```sh
rm -rf book-dir
tools/fatul.py decode book-dir/book my-exported-book.txt
```

It's important to completely remove the old directory before splitting otherwise removed/renamed blueprints will remain in the previous form and be re-introduced when the book is next built.

### Encode a Blueprint Book

```sh
tools/fatul.py encode -v book-dir/book my-book.txt
```

### Decode a Single Blueprint

```sh
tools/fatul.py decode blueprint.json my-exported-blueprint.txt
```

### Encode a Single Blueprint

```sh
tools/fatul.py encode book-dir/book/blueprint.json my-exported-blueprint.txt
```
