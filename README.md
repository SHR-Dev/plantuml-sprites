# Plantuml Sprite

## Using

include the `index.iuml` of your choice into your diagram, or include a specific sprite.

avoid includeing unnecessary files.  They can greatly slow down rendering times.

A few theme files are also included, that use common settings.  I recommend using the main theme.iuml, as it will make the sprites look better (card backgrounds transparent.)

## Adding

To add more sprites, Fork this repo, Create a `config.yaml` for the directory of your source images, and run `make_sprite.py <config.yaml>` it will create or update a directory under dist.

**Do not commit the source images**, instead just comment in your config.yaml with the location of them


