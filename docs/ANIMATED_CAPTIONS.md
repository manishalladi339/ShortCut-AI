# Animated Captions

ShortCut captions remain ordinary versioned ProjectState cues. Animation is stored
inside the existing caption `style` object and rendered deterministically through
ASS, so motion does not create a second hidden caption system.

## Supported animation values

- `none` / static
- `fade`
- `pop`
- `slide_up`

Unknown values fall back to a static caption position rather than being passed
through as raw ASS tags.

## Supported presets

### default
Balanced bold white text with a standard outline.

### minimal
Thinner outline for a cleaner subtitle look.

### social
Slightly larger, heavier outlined text designed for short-form vertical content.

## Create With Me examples

Natural-language requests include:

- “Make the captions pop”
- “Fade the captions in”
- “Slide the captions up”
- “Use bold social captions”
- “Make the captions static”

The constrained editor still applies scope containment. A caption is restyled only
when the complete cue fits inside the approved time range.

## Creator Memory

Applied `update_caption` operations contribute animation evidence.

When enough caption evidence exists, Creator Memory can carry the learned
`animation` value into future AI Director caption operations alongside:

- preset;
- size scale;
- vertical position.

This means repeated approved choices such as “pop captions” can become a learned
creator preference rather than a setting the creator re-enters every project.

## Rendering safety

The renderer:

- escapes caption text before writing ASS;
- clamps font scaling;
- generates animation tags itself;
- never interprets an arbitrary animation string as raw ASS;
- adapts animation timing to each cue duration.

Pop uses bounded scale transforms, fade uses ASS fade timing, and slide-up uses a
bounded `move` from below the final position.

Caption text itself is unchanged.
