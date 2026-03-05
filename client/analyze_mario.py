"""Analyze Mario body part regions for precise manipulation."""
from PIL import Image
import numpy as np

img = Image.open('mario_assets/Mario_New_Super_Mario_Bros_U_Deluxe.webp').convert('RGBA')
arr = np.array(img)

# Remove background
corners = [arr[0,0,:3], arr[0,-1,:3], arr[-1,0,:3], arr[-1,-1,:3]]
bg = np.mean(corners, axis=0)
dist = np.sqrt(np.sum((arr[:,:,:3].astype(float) - bg)**2, axis=2))
mask = dist < 30
arr[mask, 3] = 0

# Crop to content
alpha = arr[:,:,3]
rows = np.any(alpha > 0, axis=1)
cols = np.any(alpha > 0, axis=0)
y1, y2 = np.where(rows)[0][[0,-1]]
x1, x2 = np.where(cols)[0][[0,-1]]
cropped = arr[y1:y2+1, x1:x2+1]

# Fit to 400x500
cr_img = Image.fromarray(cropped)
cr_img.thumbnail((380, 480), Image.LANCZOS)
canvas = Image.new('RGBA', (400, 500), (0,0,0,0))
ox = (400 - cr_img.width) // 2
oy = (500 - cr_img.height) // 2
canvas.paste(cr_img, (ox, oy), cr_img)
canvas.save('mario_3d_assets/expressive/_base_prepared.png')
arr = np.array(canvas)
h, w = arr.shape[:2]
print(f'Prepared size: {w}x{h}')
print(f'Mario pasted at offset: ({ox}, {oy}), size: ({cr_img.width}, {cr_img.height})')

r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
visible = a > 128

# Red regions (hat, shirt)
red_mask = visible & (r > 150) & (g < 80) & (b < 80)
red_coords = np.where(red_mask)
if len(red_coords[0]) > 0:
    print(f'RED (hat/shirt): y=[{red_coords[0].min()}-{red_coords[0].max()}], x=[{red_coords[1].min()}-{red_coords[1].max()}]')

# Blue regions (overalls)
blue_mask = visible & (b > 120) & (r < 100) & (g < 100)
blue_coords = np.where(blue_mask)
if len(blue_coords[0]) > 0:
    print(f'BLUE (overalls): y=[{blue_coords[0].min()}-{blue_coords[0].max()}], x=[{blue_coords[1].min()}-{blue_coords[1].max()}]')

# Skin regions
skin_mask = visible & (r > 180) & (g > 130) & (g < 200) & (b > 80) & (b < 160)
skin_coords = np.where(skin_mask)
if len(skin_coords[0]) > 0:
    print(f'SKIN (face): y=[{skin_coords[0].min()}-{skin_coords[0].max()}], x=[{skin_coords[1].min()}-{skin_coords[1].max()}]')

# White regions (gloves)
white_mask = visible & (r > 200) & (g > 200) & (b > 200)
white_coords = np.where(white_mask)
if len(white_coords[0]) > 0:
    print(f'WHITE (gloves): y=[{white_coords[0].min()}-{white_coords[0].max()}], x=[{white_coords[1].min()}-{white_coords[1].max()}]')

# Brown regions
brown_mask = visible & (r > 100) & (r < 180) & (g > 40) & (g < 110) & (b < 80)
brown_coords = np.where(brown_mask)
if len(brown_coords[0]) > 0:
    print(f'BROWN (shoes/hair): y=[{brown_coords[0].min()}-{brown_coords[0].max()}], x=[{brown_coords[1].min()}-{brown_coords[1].max()}]')

# Dark regions
dark_mask = visible & (r < 60) & (g < 60) & (b < 60)
dark_coords = np.where(dark_mask)
if len(dark_coords[0]) > 0:
    print(f'DARK (mustache/outline): y=[{dark_coords[0].min()}-{dark_coords[0].max()}], x=[{dark_coords[1].min()}-{dark_coords[1].max()}]')

# Yellow (buttons)
yellow_mask = visible & (r > 200) & (g > 180) & (b < 80)
yellow_coords = np.where(yellow_mask)
if len(yellow_coords[0]) > 0:
    print(f'YELLOW (buttons): y=[{yellow_coords[0].min()}-{yellow_coords[0].max()}], x=[{yellow_coords[1].min()}-{yellow_coords[1].max()}]')

# Face region
overall_top = blue_coords[0].min() if len(blue_coords[0]) > 0 else h
face_skin = skin_mask & (np.arange(h)[:,None] < overall_top)
face_coords = np.where(face_skin)
if len(face_coords[0]) > 0:
    print(f'FACE (skin above overalls): y=[{face_coords[0].min()}-{face_coords[0].max()}], x=[{face_coords[1].min()}-{face_coords[1].max()}]')
    face_y_min = face_coords[0].min()
    face_y_max = face_coords[0].max()
else:
    face_y_min, face_y_max = 0, h//3

# Eyes
eye_blue = visible & (b > 150) & (r < 100) & (g < 100)
eye_blue = eye_blue & (np.arange(h)[:,None] >= face_y_min) & (np.arange(h)[:,None] <= face_y_max)
eye_coords = np.where(eye_blue)
if len(eye_coords[0]) > 0:
    print(f'EYES (blue in face): y=[{eye_coords[0].min()}-{eye_coords[0].max()}], x=[{eye_coords[1].min()}-{eye_coords[1].max()}]')
    eye_x_center = (eye_coords[1].min() + eye_coords[1].max()) // 2
    left_eye = eye_coords[1] < eye_x_center
    right_eye = eye_coords[1] > eye_x_center
    if np.any(left_eye):
        print(f'  LEFT EYE: y=[{eye_coords[0][left_eye].min()}-{eye_coords[0][left_eye].max()}], x=[{eye_coords[1][left_eye].min()}-{eye_coords[1][left_eye].max()}]')
    if np.any(right_eye):
        print(f'  RIGHT EYE: y=[{eye_coords[0][right_eye].min()}-{eye_coords[0][right_eye].max()}], x=[{eye_coords[1][right_eye].min()}-{eye_coords[1][right_eye].max()}]')

# Mouth
face_mid_y = (face_y_min + face_y_max) // 2
mouth_dark = dark_mask & (np.arange(h)[:,None] > face_mid_y) & (np.arange(h)[:,None] < face_y_max + 10)
mouth_coords = np.where(mouth_dark)
if len(mouth_coords[0]) > 0:
    print(f'MOUTH area (dark in lower face): y=[{mouth_coords[0].min()}-{mouth_coords[0].max()}], x=[{mouth_coords[1].min()}-{mouth_coords[1].max()}]')

# Arms
red_y = red_coords[0] if len(red_coords[0]) > 0 else np.array([])
red_x = red_coords[1] if len(red_coords[0]) > 0 else np.array([])
left_arm = (red_x < w//2 - 30) & (red_y > face_y_min)
right_arm = (red_x > w//2 + 30) & (red_y > face_y_min)
if np.any(left_arm):
    print(f'LEFT ARM (red, left side): y=[{red_y[left_arm].min()}-{red_y[left_arm].max()}], x=[{red_x[left_arm].min()}-{red_x[left_arm].max()}]')
if np.any(right_arm):
    print(f'RIGHT ARM (red, right side): y=[{red_y[right_arm].min()}-{red_y[right_arm].max()}], x=[{red_x[right_arm].min()}-{red_x[right_arm].max()}]')

# Gloves
left_glove = white_mask & (np.arange(w)[None,:] < w//2 - 20) & (np.arange(h)[:,None] > face_y_max)
right_glove = white_mask & (np.arange(w)[None,:] > w//2 + 20) & (np.arange(h)[:,None] > face_y_max)
lg_coords = np.where(left_glove)
rg_coords = np.where(right_glove)
if len(lg_coords[0]) > 0:
    print(f'LEFT GLOVE: y=[{lg_coords[0].min()}-{lg_coords[0].max()}], x=[{lg_coords[1].min()}-{lg_coords[1].max()}]')
if len(rg_coords[0]) > 0:
    print(f'RIGHT GLOVE: y=[{rg_coords[0].min()}-{rg_coords[0].max()}], x=[{rg_coords[1].min()}-{rg_coords[1].max()}]')

# Hat
hat_red = red_mask & (np.arange(h)[:,None] < face_y_min + 10)
hat_coords = np.where(hat_red)
if len(hat_coords[0]) > 0:
    print(f'HAT (red above face): y=[{hat_coords[0].min()}-{hat_coords[0].max()}], x=[{hat_coords[1].min()}-{hat_coords[1].max()}]')

# Shoes
shoe_coords = np.where(brown_mask & (np.arange(h)[:,None] > h * 0.8))
if len(shoe_coords[0]) > 0:
    print(f'SHOES (brown, bottom): y=[{shoe_coords[0].min()}-{shoe_coords[0].max()}], x=[{shoe_coords[1].min()}-{shoe_coords[1].max()}]')

# Print some sample pixel values at key locations
print(f'\n--- Sample pixels ---')
for label, sy, sx in [('Center face', (face_y_min+face_y_max)//2, w//2),
                       ('Eye area', face_y_min + (face_y_max-face_y_min)//3, w//2),
                       ('Mouth area', face_y_max - 5, w//2)]:
    if 0 <= sy < h and 0 <= sx < w:
        print(f'{label} ({sx},{sy}): RGBA={tuple(arr[sy, sx])}')
