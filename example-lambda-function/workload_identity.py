#!/usr/bin/python
from google.cloud import vision

def vision_api_test():
    image_uri = 'https://storage.googleapis.com/cloud-samples-data/vision/using_curl/shanghai.jpeg'

    client = vision.ImageAnnotatorClient()
    image = vision.Image()
    image.source.image_uri = image_uri

    response = client.label_detection(image=image)
    print('########## Showing access to Vision API data ##########')
    print('Labels (and confidence score):')
    print('=' * 30)
    for label in response.label_annotations:
        print(label.description, '(%.2f%%)' % (label.score*100.))

def lambda_handler(event=None, context=None):
    vision_api_test()