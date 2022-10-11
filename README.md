this is a garbage program to view a tree of reward pools in Anno 1800

useful for some mod authors


# anno\_goats

Anno 1800's .rda archives contain an XML document at
data\config\export\main\asset\assets.xml with a bunch of `<Asset>` elements for
items and reward pools that contain items or other reward pools.

Pools are a big mess for a number of reasons, including:

- Since pools can have membership in other pools, items added to two
  *different* pools can end up in the *same* pool twice if one pool includes the other pool.

- Item membership is conflated with weighting sampling for rewards.

## wow

It's really bananas trying to make sense of item membership and item sampling
so this tool tries to help visualize two things:

- what items are in what pools

- what pools contain what items

## picture of great effort

A pool containing a bunch of other pools that also contain pools and also items
and sometimes things have different weights.  The percentages shown are based
on the weights and my (mis)understanding of the wacky reward pool system.

![a tree of all items and pools in the La Fortune Item Drop Pool including weights and estimated reward sampling probability](https://cdn.discordapp.com/attachments/512145176161157121/1029240527788441670/lafortune-drop-pool.png)

A list of all `<Asset>`s in the loaded XML document that have an `<Item>` or
`<RewardPool>` element.  Right click on a row to either view the pools that
have that item or the items in that pool.

Also this shows filtering on the bottom that lets you match by GUID (`Values/Standard/GUID`) or Name (`Values/Standard/Name`).

![context menu of Flippy hovering "show pools with selected item"](https://cdn.discordapp.com/attachments/512145176161157121/1029237281246158898/all-items-with-filter.png)

Pools containing the asset recursively. Like the inverse of the first image.

![a tree of pools containing Flippy](https://cdn.discordapp.com/attachments/512145176161157121/1029237280889638923/pools-with-flipppy.png)

## running the program

This software is written in Python 3 and uses Qt 6 via the PySide6 bindings.

I used run pyinstaller and it made a single executable that maybe runs on
windows computers without installing a bunch of stuff.

maybe it's on a github at [github.com/sqwishy/anno\_goats/releases](https://github.com/sqwishy/anno_goats/releases)

Or if you have Python you can maybe install it with pip.

## usage

This reads an assets.xml so if you run the exe it'll prompt you for one.  Or I
think you can "open with...".  Or drag and drop an assets.xml onto the main
window.

You can use the vanilla assets.xml by using something like RDA Explorer to
unpack it from the archives?

Or use xmltest from xforce's modloader to apply a mod to assets.xml and open
the resulting patched.xml file to view the assets with a mod applied to it.

i don't have a GUI for that though :C

glhf

## find your goat

![find your goat](https://cdn.discordapp.com/attachments/512145176161157121/1029237281657200710/goat.png)
