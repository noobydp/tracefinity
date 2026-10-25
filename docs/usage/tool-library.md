# Tool Library

Every tool you save from a trace session goes into your library on the app home page. Tools are shown as a grid. Hover a card to see the outline preview instead of the photo.

## Tool dimensions

Tools show a reference minimum width × depth in Gridfinity units, followed by
their measured height. The reference footprint uses the saved outline's
orientation, standard walls and stacking lip, 1 mm clearance and whole-grid
sizing. It includes the same wall/lip inset and clearance as automatic bin
sizing; different bin settings can change the required footprint. Inside the
bin editor's tool picker, the measurement uses that bin's current settings,
including half-grid sizing. It updates when the outline or settings change.

**Height not set** means unknown, not zero. Enter the physical tool thickness
in the tool editor; photos cannot determine it. Height is information for
planning and does not change saved bin heights or pocket depths.

## Filtering by size

Expand **Filter by size** and enter minimum and/or maximum grid width, grid
depth or measured tool height. Limits are inclusive and combine with name
search and placement status. Footprints use the reference settings and saved
orientation described above; the filter does not rotate tools. Tools with
unknown height remain visible unless a height limit is set. A footprint limit
excludes tools whose outline is missing.

Leave either bound blank for no limit. Invalid or reversed ranges show an
error and pause size filtering while name/status filtering continues. **Clear
size filters** removes all size limits without clearing other filters.

## Actions

- **Open the editor** -- click a tool to edit its outline, add cutouts, or transform it.
- **Search** -- filter tools by name (case-insensitive).
- **Sort** -- by date created or alphabetically.
- **Tags** -- use **Filter by tag** alongside name search and the placement-status filters. Tags appear on tool cards; edit them in the tool editor.
- **Rename** -- click the tool name to edit it inline.
- **Delete** -- remove the tool permanently.

## Assignment and placement

Each tool card shows which project it belongs to and whether it has been placed in a bin. Tools marked "placed" are already in a bin layout; those marked "needs bin" still need one.

Click the project indicator to go directly to that project's view.

## Reusing tools

Tools are reusable across multiple bins. Trace a tool once, then drop it into as many bin layouts as you need.
