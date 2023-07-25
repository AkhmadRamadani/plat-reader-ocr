import cv2
import matplotlib.pyplot as plt
import numpy as np
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import db as firebase_db
from firebase_admin import storage
import datetime
import pytz
import os
from flask import Flask, request, render_template, jsonify
from predict import predict, predict64
import re
import base64
import ssl
import numpy as np
from flask_cors import CORS

app = Flask(__name__)
timezone = pytz.timezone('Asia/Jakarta')
cred = credentials.Certificate('detect-plat-8e807-firebase-adminsdk-u7tp3-182a70c2f1.json')

firebase_db_url = 'https://detect-plat-8e807-default-rtdb.firebaseio.com'
firebase_storage_bucket = 'detect-plat-8e807.appspot.com'

# Initialize Firebase
firebase_admin.initialize_app(cred, {
    'storageBucket': firebase_storage_bucket,
    'databaseURL': firebase_db_url
})

db = firestore.client()
firebase_db_ref = firebase_db.reference(app=firebase_admin.get_app())

# Initialize Firebase Storage
storage_bucket = storage.bucket(app=firebase_admin.get_app())

@app.route('/', methods=['GET'])
def index():
    return 'Hi, World!'

@app.route('/test', methods=['GET'])
def testing():
    return jsonify({
        'test': 'afasfsa'
    })

@app.route('/predict64', methods=['POST'])
def predictPlat64():
    try:
        data = request.get_json(force=True)
        image = data['image']

        base64Image = re.sub('^data:image/.+;base64,', '', image)
        base64Image = base64Image.replace(' ', '+')
        base64Image = base64Image.encode()
        base64Image = base64.b64decode(base64Image)

        # Upload image to Firebase Storage
        image_name = datetime.datetime.now(timezone).strftime("%Y-%m-%d_%H-%M-%S") + '.jpg'
        blob = storage_bucket.blob(image_name)
        blob.upload_from_string(base64Image, content_type='image/jpg')
        print("Gambar berhasil diunggah ke Firebase Storage.")

        predict_data = predict64(base64Image)

        user_ref = db.collection('plat')
        user_docs = user_ref.get()

        matched_username = None

        for user_doc in user_docs:
            data_firestore = user_doc.to_dict()
            plat_nomor_firestore = data_firestore['plat']

            if plat_nomor_firestore == predict_data:
                matched_username = data_firestore['userId']
                print("Plat nomor cocok pada kendaraan milik", matched_username)
                break

        if matched_username:
            current_time = datetime.datetime.now(timezone)

            log_ref = db.collection('log')
            log_docs = log_ref.where('plat', '==', predict_data).get()

            for log_doc in log_docs:
                log_data_firestore = log_doc.to_dict()
                if 'masuk' in log_data_firestore and 'keluar' in log_data_firestore:
                    log_data = {
                        'masuk': current_time,
                        'nama': matched_username,
                        'plat': predict_data,
                        'akses': 1
                    }
                    db.collection('log').add(log_data)
                    print("Membuat data log baru.")
                else:
                    log_doc.reference.update({
                        'keluar': current_time,
                        'akses': 2
                    })
                    print("Data log diperbarui.")
                    break
            else:
                log_data = {
                    'masuk': current_time,
                    'nama': matched_username,
                    'plat': predict_data,
                    'akses': 1
                }
                db.collection('log').add(log_data)
                print("Data log masuk telah ditambahkan ke Firestore.")

            # Insert ke Realtime Database
            realtime_db_ref = firebase_db_ref.child('kontrol')
            realtime_db_ref.set(1)
            print("Data 'kontrol' berhasil ditambahkan ke Realtime Database.")
        else:
            print(predict_data)
            print("Plat nomor tidak cocok dengan data pengguna yang ada.")

        return jsonify({
            "prediction": predict_data
        }), 200
    except KeyError:
        return jsonify({
            "error": "Invalid data format. 'image' key not found in JSON."
        }), 400
    except Exception as e:
        print(e)
        return jsonify({
            "error": "Internal Server Error."
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=8000), host='0.0.0.0', ssl_context='adhoc')
