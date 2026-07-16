import numpy as np

#주요 관절 포인트
ANGLE_JOINTS = {
    'r_elbow':    (12, 14, 16),
    'l_elbow':    (11, 13, 15),
    'r_shoulder': (14, 12, 24),
    'l_shoulder': (13, 11, 23),
    'r_knee':     (24, 26, 28),
    'l_knee':     (23, 25, 27),
    'r_wrist':    (14, 16, 18),  # 팔꿈치→손목→오른쪽 엄지 (18번)
    'l_wrist':    (13, 15, 17),  # 팔꿈치→손목→왼쪽 엄지 (17번)
}

def calculate_angle(a, b, c):
    """
    세 점의 x, y 좌표를 받아 사이 각도(degrees)를 계산.
    (b점이 각도의 꼭짓점입니다.)
    """
    a = np.array(a) # 첫 번째 점
    b = np.array(b) # 꼭짓점 (예: 팔꿈치나 무릎)
    c = np.array(c) # 세 번째 점

    # 1. 꼭짓점을 기준으로 두 개의 선(벡터)을 만듬.
    v1 = a - b
    v2 = c - b

    # 2. 두 선이 이루는 각도를 삼각함수(코사인 제2법칙)로 계산.
    cosine_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0) # 계산 오차 방지
    
    # 3. 라디안 값을 우리가 아는 '도(degree)'로 변경.
    angle_rad = np.arccos(cosine_angle)
    angle_deg = np.degrees(angle_rad)

    # 4. 180도 이하의 내각 사용.
    if angle_deg > 180.0:
        angle_deg = 360 - angle_deg

    return angle_deg

def calculate_angle_without_z(a, b, c):
    """
    세 점의 x, y 좌표를 받아 사이 각도(degrees)를 계산.
    (b점이 각도의 꼭짓점)
    """
    # 원본 3D 좌표에서 Z축을 버리고 X[0], Y[1] 좌표만 가져와 2D 평면으로 제작.
    a = np.array([a[0], a[1]]) 
    b = np.array([b[0], b[1]]) 
    c = np.array([c[0], c[1]]) 

    # 1. 꼭짓점을 기준으로 두 개의 선(벡터)을 만듬.
    v1 = a - b
    v2 = c - b

    # 2. 두 선이 이루는 각도를 삼각함수(코사인 제2법칙)로 계산.
    cosine_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0) # 계산 오차 방지
    
    # 3. 라디안 값을 우리가 아는 '도(degree)'로 변경.
    angle_rad = np.arccos(cosine_angle)
    angle_deg = np.degrees(angle_rad)

    # 180도 이하의 내각 사용.
    if angle_deg > 180.0:
        angle_deg = 360 - angle_deg

    return angle_deg

#상하체의 꼬임 각도를 구함
def calculate_x_factor(s_left, s_right, h_left, h_right):
    #어깨선 벡터
    vec_shoulder = np.array([s_right[0] - s_left[0], s_right[2] - s_left[2]])
    #골반선 벡터
    vec_hip = np.array([h_right[0] - h_left[0], h_right[2] - h_left[2]])

    #0도 기준선과 이루는 절대 각도를 구함
    angle_shoulder = np.degrees(np.arctan2(vec_shoulder[1], vec_shoulder[0]))
    angle_hip = np.degrees(np.arctan2(vec_hip[1], vec_hip[0]))

    x_factor = abs(angle_shoulder - angle_hip)

    if x_factor > 180.0:
        x_factor = 360.0 - x_factor
    
    return x_factor


def normalize_by_pelvis(landmarks):
    """
    33개의 뼈대 좌표를 받아, '골반의 중심'을 (0, 0) 원점으로 영점 조절합니다.
    카메라가 멀리 있든 가까이 있든, 체격이 크든 작든 공평하게 움직임을 비교할 수 있습니다.
    """
    # MediaPipe에서 23번은 왼쪽 엉덩이(골반), 24번은 오른쪽 엉덩이.
    left_hip = landmarks[23]
    right_hip = landmarks[24]
    
    # 1. 두 엉덩이의 정중앙(배꼽 살짝 아래) 좌표를 찾음. 여기가 새로운 기준점(0,0)
    pelvis_x = (left_hip.x + right_hip.x) / 2
    pelvis_y = (left_hip.y + right_hip.y) / 2
    pelvis_z = (left_hip.z + right_hip.z) / 2
    
    normalized_points = []
    
    # 2. 33개의 모든 관절 좌표에서 기준점의 위치만큼 뺌. (영점 조절)
    for lm in landmarks:
        norm_x = lm.x - pelvis_x
        norm_y = lm.y - pelvis_y
        norm_z = lm.z - pelvis_z
        normalized_points.append((norm_x, norm_y, norm_z))
        
    return normalized_points

def normalize_by_pelvis_csv(row):
    #csv에서 행을 읽어 골반 기준 정규화

    pelvis_x =  (row['x23'] + row['x24']) / 2
    pelvis_y =  (row['y23'] + row['y24']) / 2
    pelvis_z =  (row['z23'] + row['z24']) / 2

    normalized = {}

    for i in range(33):
        normalized[f'x{i}'] = row[f'x{i}'] - pelvis_x
        normalized[f'y{i}'] = row[f'y{i}'] - pelvis_y
        normalized[f'z{i}'] = row[f'z{i}'] - pelvis_z
        normalized[f'v{i}'] = row[f'v{i}']
    
    return normalized