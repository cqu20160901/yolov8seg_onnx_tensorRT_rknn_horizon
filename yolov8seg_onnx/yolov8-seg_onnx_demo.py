#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from math import exp

import cv2
import numpy as np
import onnxruntime as ort

CLASSES = ['person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat', 'traffic light',
         'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
         'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
         'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
         'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
         'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
         'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
         'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
         'hair drier', 'toothbrush']


color_dict = {
    0: (000, 000, 255),
    1: (255, 128, 000),
    2: (255, 255, 000),
    3: (000, 255, 000),
    4: (000, 255, 255),
    5: (255, 000, 000),
    6: (128, 000, 255),
    7: (255, 000, 255),
    8: (128, 000, 000),
    9: (000, 128, 000),
}


meshgrid = []

class_num = len(CLASSES)
headNum = 3
strides = [8, 16, 32]
mapSize = [[80, 80], [40, 40], [20, 20]]
nmsThresh = 0.45
objectThresh = 0.5

input_imgH = 640
input_imgW = 640

maskNum = 32


class DetectBox:
    def __init__(self, classId, score, xmin, ymin, xmax, ymax, mask):
        self.classId = classId
        self.score = score
        self.xmin = xmin
        self.ymin = ymin
        self.xmax = xmax
        self.ymax = ymax
        self.mask = mask


def GenerateMeshgrid():
    for index in range(headNum):
        for i in range(mapSize[index][0]):
            for j in range(mapSize[index][1]):
                meshgrid.append(j + 0.5)
                meshgrid.append(i + 0.5)


def IOU(xmin1, ymin1, xmax1, ymax1, xmin2, ymin2, xmax2, ymax2):
    xmin = max(xmin1, xmin2)
    ymin = max(ymin1, ymin2)
    xmax = min(xmax1, xmax2)
    ymax = min(ymax1, ymax2)

    innerWidth = xmax - xmin
    innerHeight = ymax - ymin

    innerWidth = innerWidth if innerWidth > 0 else 0
    innerHeight = innerHeight if innerHeight > 0 else 0

    innerArea = innerWidth * innerHeight

    area1 = (xmax1 - xmin1) * (ymax1 - ymin1)
    area2 = (xmax2 - xmin2) * (ymax2 - ymin2)

    total = area1 + area2 - innerArea

    return innerArea / total


def NMS(detectResult):
    predBoxs = []

    sort_detectboxs = sorted(detectResult, key=lambda x: x.score, reverse=True)

    for i in range(len(sort_detectboxs)):
        xmin1 = sort_detectboxs[i].xmin
        ymin1 = sort_detectboxs[i].ymin
        xmax1 = sort_detectboxs[i].xmax
        ymax1 = sort_detectboxs[i].ymax
        classId = sort_detectboxs[i].classId

        if sort_detectboxs[i].classId != -1:
            predBoxs.append(sort_detectboxs[i])
            for j in range(i + 1, len(sort_detectboxs), 1):
                if classId == sort_detectboxs[j].classId:
                    xmin2 = sort_detectboxs[j].xmin
                    ymin2 = sort_detectboxs[j].ymin
                    xmax2 = sort_detectboxs[j].xmax
                    ymax2 = sort_detectboxs[j].ymax
                    iou = IOU(xmin1, ymin1, xmax1, ymax1, xmin2, ymin2, xmax2, ymax2)
                    if iou > nmsThresh:
                        sort_detectboxs[j].classId = -1
    return predBoxs


def sigmoid(x):
    return 1 / (1 + exp(-x))


def postprocess(out, img_h, img_w):
    print('postprocess ... ')

    detectResult = []
    output = []
    for i in range(len(out)):
        output.append(out[i].reshape((-1)))

    scale_h = img_h / input_imgH
    scale_w = img_w / input_imgW

    gridIndex = -2

    for index in range(headNum):
        reg = output[index * 2 + 0]
        cls = output[index * 2 + 1]
        msk = output[6 + index]

        for h in range(mapSize[index][0]):
            for w in range(mapSize[index][1]):
                gridIndex += 2

                for cl in range(class_num):
                    cls_val = sigmoid(cls[cl * mapSize[index][0] * mapSize[index][1] + h * mapSize[index][1] + w])

                    if cls_val > objectThresh:
                        x1 = (meshgrid[gridIndex + 0] - reg[0 * mapSize[index][0] * mapSize[index][1] + h * mapSize[index][1] + w]) * strides[index]
                        y1 = (meshgrid[gridIndex + 1] - reg[1 * mapSize[index][0] * mapSize[index][1] + h * mapSize[index][1] + w]) * strides[index]
                        x2 = (meshgrid[gridIndex + 0] + reg[2 * mapSize[index][0] * mapSize[index][1] + h * mapSize[index][1] + w]) * strides[index]
                        y2 = (meshgrid[gridIndex + 1] + reg[3 * mapSize[index][0] * mapSize[index][1] + h * mapSize[index][1] + w]) * strides[index]

                        xmin = x1 * scale_w
                        ymin = y1 * scale_h
                        xmax = x2 * scale_w
                        ymax = y2 * scale_h

                        xmin = xmin if xmin > 0 else 0
                        ymin = ymin if ymin > 0 else 0
                        xmax = xmax if xmax < img_w else img_w
                        ymax = ymax if ymax < img_h else img_h

                        mask = []
                        for m in range(maskNum):
                            mask.append(msk[m * mapSize[index][0] * mapSize[index][1] + h * mapSize[index][1] + w])

                        box = DetectBox(cl, cls_val, xmin, ymin, xmax, ymax, mask)
                        detectResult.append(box)
    # NMS
    print('detectResult:', len(detectResult))
    predBox = NMS(detectResult)

    return predBox


def seg_postprocess(out, predbox, img_h, img_w):
    print('seg_postprocess ... ')
    protos = np.array(out[-1][0])

    c, mh, mw = protos.shape
    seg_mask = np.zeros(shape=(mh, mw, 3))

    for i in range(len(predbox)):
        masks_in = np.array(predbox[i].mask).reshape(-1, c)
        masks = (masks_in @ protos.reshape(c, -1))

        masks = 1 / (1 + np.exp(-masks))
        masks = masks.reshape(mh, mw)

        xmin = int(predbox[i].xmin / img_w * mw + 0.5)
        ymin = int(predbox[i].ymin / img_h * mh + 0.5)
        xmax = int(predbox[i].xmax / img_w * mw + 0.5)
        ymax = int(predbox[i].ymax / img_h * mh + 0.5)
        classId = predbox[i].classId
        for h in range(ymin, ymax):
            for w in range(xmin, xmax):
                if masks[h, w] > 0.5:
                    seg_mask[h, w, :] = color_dict[classId % 9]

    seg_mask = cv2.resize(seg_mask, (img_w, img_h))
    seg_mask = seg_mask.astype("uint8")
    return seg_mask


def precess_image(img_src, resize_w, resize_h):
    image = cv2.resize(img_src, (resize_w, resize_h), interpolation=cv2.INTER_LINEAR)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = image.astype(np.float32)
    image /= 255
    return image


def detect(img_path):

    orig = cv2.imread(img_path)
    img_h, img_w = orig.shape[:2]
    image = precess_image(orig, input_imgW, input_imgH)

    image = image.transpose((2, 0, 1))
    image = np.expand_dims(image, axis=0)

    ort_session = ort.InferenceSession('./yolov8n-seg_relu_80class_zq.onnx')
    pred_results = (ort_session.run(None, {'data': image}))

    out = []
    for i in range(len(pred_results)):
        print(pred_results[i].shape)
        print(pred_results[i].reshape(-1).shape)
        print('----------------')
        out.append(pred_results[i])
    predbox = postprocess(out, img_h, img_w)

    mask = seg_postprocess(out, predbox, img_h, img_w)

    print('obj num is :', len(predbox))

    for i in range(len(predbox)):
        xmin = int(predbox[i].xmin)
        ymin = int(predbox[i].ymin)
        xmax = int(predbox[i].xmax)
        ymax = int(predbox[i].ymax)
        classId = predbox[i].classId
        score = predbox[i].score

        cv2.rectangle(orig, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
        ptext = (xmin, ymin)
        title = CLASSES[classId] + "%.2f" % score
        cv2.putText(orig, title, ptext, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)

    result_img = np.clip(np.array(orig) + np.array(mask) * 0.8, a_min=0, a_max=255)
    cv2.imwrite('./test_onnx_result.jpg', result_img)


if __name__ == '__main__':
    print('This is main ....')
    GenerateMeshgrid()
    img_path = './test.jpg'
    detect(img_path)


