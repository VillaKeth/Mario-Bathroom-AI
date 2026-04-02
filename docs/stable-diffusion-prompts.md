# Stable Diffusion Prompts for Mario Bathroom Backgrounds

## Prompt 1: Realistic 1985 Florida Bathroom
"1985 Florida townhouse apartment bathroom interior, fiberglass tub/shower combo, single vanity with laminate countertop, vinyl flooring, builder-grade fixtures, warm fluorescent lighting, 2-bedroom apartment in Gainesville FL, clean, lived-in feel, slightly dated but well-maintained"
Negative: "modern, luxury, marble, fancy, outdoor"
Model: SDXL 1.0, Steps: 30, CFG: 7

## Prompt 2: Mario-Themed Bathroom
"Super Mario themed bathroom, green pipes as towel racks, question block soap dispenser, mushroom bath mat, retro Nintendo wallpaper border, 1985 Florida apartment base, warm lighting"
Negative: "dark, scary, horror, realistic mario"

## Prompt 3: Party Night Bathroom  
"Party-decorated apartment bathroom, streamers and balloons, LED string lights, birthday decorations, clean bathroom, warm festive lighting, slightly hazy atmosphere"
Negative: "dirty, messy, gross, dark, horror"

## Usage Instructions

1. Generate images at 800x600 resolution to match the Mario AI window dimensions
2. Save images as `.png` or `.jpg` files in the `client/assets/backgrounds/` directory
3. The Mario AI client will automatically detect and load any images in this directory
4. Use the `next_background()` method or relevant keyboard shortcut to cycle through backgrounds
5. Images are automatically scaled to fit the window size

## Background Cycling Order

The system cycles through backgrounds in this order:
1. Default drawn bathroom scene (original code-generated background)
2. First image in alphabetical order from `client/assets/backgrounds/`
3. Second image in alphabetical order
4. ... (continues through all images)
5. Back to drawn background (cycles infinitely)

## Technical Notes

- Images are loaded once on startup for performance
- Backgrounds are cached as surfaces to avoid repeated loading during rendering
- The system gracefully handles missing background directories or failed image loads
- All standard image formats supported by pygame are compatible (PNG, JPG, JPEG)