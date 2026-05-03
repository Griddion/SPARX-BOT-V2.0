import base64

# encodes the image into base 64 for the image url for the AI
def encode_image(img_path):
    with open(img_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')
