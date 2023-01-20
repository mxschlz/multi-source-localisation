from labplatform.config import get_config
from labplatform.core.Setting import DeviceSetting
from labplatform.core.Device import Device
from traits.api import Instance, Float, Any, Str, List, Tuple, Bool
from PIL import ImageEnhance, Image
from labplatform.core import TDTblackbox as tdt
import logging
try:
    from headpose.detect import PoseEstimator
except ModuleNotFoundError:
    logging.info("WARNING: headpose package not found, maybe try reinstalling: pip install headpose")
import numpy as np
from Speakers.speaker_config import SpeakerArray
import os
import PySpin
from simple_pyspin import Camera
import cv2
import PIL
from matplotlib import pyplot as plt
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

log = logging.getLogger(__name__)

class ArUcoCamSetting(DeviceSetting):
    """
    Class for defining the camera settings. primary group parameters are supposed to be changed and sometimes
    reinitialized, whereas status group parameters are not.
    """
    type = Str("image", group="status", dsec="nature of the signal")
    dtype = Instance(np.uint8, group="status", dsec="data type")
    shape = Tuple(1080, 1440, group="primary", dsec="default shape of the image", reinit=False)
    root = Str(get_config(setting="BASE_DIRECTORY"), group="status", dsec="Labplatform root directory")
    setup = Str("dome", group="status", dsec="experiment setup")
    file = Str(f"{setup.default_value}_speakers.txt", group="status", dsec="Speaker file")
    pose = List(group="primary", dsec="Headpose", reinit=False)
    device_name = Str("FireFly", group="status", dsec="Name of the device")
    device_type = Str("Camera", group='status', dsec='Type of the device')


class ArUcoCam(Device):
    """
    Class for controlling the device. We set the setting class as this classes attribute (.setting). Also we have
    placeholders for the offset of the camera, the pose for each trial, the PoseEstimator (CNN), the cam itself and the
    tdt handle, mainly for calibration.
    """
    setting = ArUcoCamSetting()
    aruco_dicts = [cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_100),
                   cv2.aruco.Dictionary_get(cv2.aruco.DICT_5X5_100)]
    params = cv2.aruco.DetectorParameters_create()
    cams = [Camera(index=0), Camera(index=1)]
    # led = Any()
    offset = Any()
    calibrated = Bool()

    def _initialize(self, **kwargs):
        """
        Initializes the device and sets the state to "created". Necessary before running the device.
        """
        for c in self.cams:  # initialize cameras
            c.init()

    def _configure(self, **kwargs):
        """
        Manipulates the setting parameters of the class and sets the state to "ready. Needs to be called in each trial.
        """
        pass

    def _start(self, **kwargs):
        """
        Runs the device and sets the state to "running". Here lie all the important steps the camera has to do in each
        trial, such as acquiring and writing the head pose.
        """
        for c in self.cams:
            c.start()  # start recording images into the camera buffer
        if self.calibrated:
            pose = self.get_pose()  # Get image as numpy array
            if self.offset:
                self.setting.pose = [pose[0] - self.offset[0], pose[1] - self.offset[1]]  # subtract offset
            else:
                log.info("Camera not calibrated, head pose might be unreliable ...")
                self.setting.pose = pose
            log.info("Acquired pose!")
        else:
            log.info("WARNING: Camera is not calibrated, head pose might be unreliable.")
            self.setting.pose = self.get_pose()

    def _pause(self, **kwargs):
        """
        Pauses the camera and sets the state to "paused".
        """
        for c in self.cams:
            c.stop()

    def _stop(self):
        """
        Closes the camera and cleans up and sets the state to "stopped".
        """
        for c in self.cams:
            c.close()

    def snapshot(self, cmap="gray"):
        """
        Args:
            cmap: matplotlib colormap
        """
        for c in self.cams:
            image = c.get_array()  # get image as np array
            plt.imshow(image, cmap=cmap)  # show image
            plt.show()

    def get_pose(self, plot=False, resolution=1.0):
        pose = [None, None]
        for i, c in enumerate(self.cams):
            image = c.get_array()
            if resolution < 1.0:
                image = self.change_res(image, resolution)
            _pose, info = self.pose_from_image(image=image, dictionary=self.aruco_dicts[i])
            if plot:
                if _pose is None:
                    image = self.draw_markers(image, _pose, self.aruco_dicts[i], info)
                cv2.imshow('camera %s' % c.DeviceID(), image)
            if _pose:
                _pose = np.asarray(_pose)[:, 2].astype('float16')
                # remove outliers
                d = np.abs(_pose - np.median(_pose))  # deviation from median
                mdev = np.median(d)  # mean deviation
                s = d / mdev if mdev else 0.  # factorized mean deviation of each element in pose
                _pose = _pose[s < 2]  # remove outliers
                _pose = np.mean(_pose)
                pose[i] = _pose
        return pose

    def pose_from_image(self, image, dictionary):  # get pose
        (corners, ids, rejected) = cv2.aruco.detectMarkers(image, dictionary=dictionary, parameters=self.params)
        if len(corners) == 0:
            return None, [0, 0, 0, 0]
        else:
            size = image.shape
            focal_length = size[1]
            center = (size[1] / 2, size[0] / 2)
            camera_matrix = np.array([[focal_length, 0, center[0]],
                                         [0, focal_length, center[1]],
                                         [0, 0, 1]], dtype="double")
            dist_coeffs = np.zeros((4, 1))  # Assuming no lens distortion
            # camera_matrix = numpy.loadtxt('mtx.txt')
            # dist_coeffs = numpy.loadtxt('dist.txt')
            rotation_vec, translation_vec, _objPoints = \
                cv2.aruco.estimatePoseSingleMarkers(corners, .05, camera_matrix, dist_coeffs)
            pose = []  # numpy.zeros([len(translation_vec), 2])
            info = []  # numpy.zeros([len(translation_vec), 4])
            for i in range(len(translation_vec)):
                rotation_mat = -cv2.Rodrigues(rotation_vec[i])[0]
                pose_mat = cv2.hconcat((rotation_mat, translation_vec[i].T))
                _, _, _, _, _, _, angles = cv2.decomposeProjectionMatrix(pose_mat)
                angles[1, 0] = np.radians(angles[1, 0])
                angles[1, 0] = np.degrees(np.arcsin(np.sin(np.radians(angles[1, 0]))))
                angles[0, 0] = -angles[0, 0]
                info.append([camera_matrix, dist_coeffs, rotation_vec[i], translation_vec[i]])
                pose.append([angles[1, 0], angles[0, 0], angles[2, 0]])
            return pose, info

    @staticmethod
    def draw_markers(image, pose, aruco_dict, info):
        marker_len = .05
        (corners, ids, rejected) = cv2.aruco.detectMarkers(image, dictionary=aruco_dict)
        if len(corners) > 0:
            for i in range(len(corners)):
                Imaxis = cv2.aruco.drawDetectedMarkers(image.copy(), corners, ids=None)
                image = cv2.aruco.drawAxis(Imaxis, info[i][0], info[i][1], info[i][2], info[i][3], marker_len)
                # info: list of arrays [camera_matrix, dist_coeffs, rotation_vec, translation_vec]
                bottomLeftCornerOfText = (20, 20 + (20 * i))
                cv2.putText(image, 'roll: %f' % (pose[i][2]),  # display heade pose
                            bottomLeftCornerOfText, cv2.FONT_HERSHEY_PLAIN, fontScale=1, color=(225, 225, 225),
                            lineType=1, thickness=1)
        return image

    @staticmethod
    def change_res(image, resolution):
        data = PIL.Image.fromarray(image)
        width = int(data.size[0] * resolution)
        height = int(data.size[1] * resolution)
        image = data.resize((width, height), PIL.Image.ANTIALIAS)
        return np.asarray(image)

    @staticmethod
    def brighten(image, factor):
        """
        Brightens the image by a factor.
        Args:
            image: image to be brightened, must be in the form of an array.
            factor: factor by which the image gets brightened.

        Returns:
            brightened image array.
        """
        img = Image.fromarray(image)  # transform array to PIL.Image object
        filter = ImageEnhance.Brightness(img)  # create brightness filter
        brightimg = filter.enhance(factor)  # enhance image
        array = np.asarray(brightimg)  # transform back to array
        return array

    @staticmethod
    def sharpen(image, factor):
        """
        Args:
            image: image to be sharpened, must be in the form of an array.
            factor: factor by which the image gets sharpened.

        Returns:
            sharpened image array.
        """
        img = Image.fromarray(image)  # transform array to PIL.Image object
        filter = ImageEnhance.Sharpness(img)  # create sharpness filter
        sharpimg = filter.enhance(factor)  # enhance image
        array = np.asarray(sharpimg)  # transform back to array
        return array


class FlirCamSetting(DeviceSetting):
    """
    Class for defining the camera settings. primary group parameters are supposed to be changed and sometimes
    reinitialized, whereas status group parameters are not.
    """
    name = Str("FireFly", group="status", dsec="")
    type = Str("image", group="primary", dsec="nature of the signal", reinit=False)
    dtype = Instance(np.uint8, group="status", dsec="data type")
    shape = Tuple(1080, 1440, group="primary", dsec="default shape of the image", reinit=False)
    sampling_freq = Float()
    root = Str(get_config(setting="BASE_DIRECTORY"), group="status", dsec="labplatform root directory")
    setup = Str("dome", group="status", dsec="experiment setup")
    file = Str(f"{setup.default_value}_speakers.txt")
    led = Any(group="primary", dsec="central speaker with attached led for initial camera calibration", reinit=False)
    calibrated = Bool(False, group="primary", dsec="tells whether camera is calibrated or not", reinit=False)


class FlirCam(Device):
    """
    Class for controlling the device. We set the setting class as this classes attribute (.setting). Also we have
    placeholders for the offset of the camera, the pose for each trial, the PoseEstimator (CNN), the cam itself and the
    tdt handle, mainly for calibration.
    """
    setting = FlirCamSetting()
    pose = List()
    offset = Float()
    try:
        est = PoseEstimator()
    except NameError:
        est = None
    cam = Any()
    handle = Any()

    def _initialize(self, **kwargs):
        """
        Initializes the device and sets the state to "created". Necessary before running the device.
        """
        spks = SpeakerArray(file=os.path.join(self.setting.root, self.setting.file))  # initialize speakers.
        spks.load_speaker_table()  # load speakertable
        self.setting.led = spks.pick_speakers(23)[0]  # pick central speaker
        self.cam = Camera()  # initialize camera from simple pyspin
        self.cam.init()  # initialize camera

    def _configure(self, **kwargs):
        """
        Manipulates the setting parameters of the class and sets the state to "ready. Needs to be called in each trial.
        """
        pass

    def _start(self, **kwargs):
        """
        Runs the device and sets the state to "running". Here lie all the important steps the camera has to do in each
        trial, such as acquiring and saving the head pose.
        """
        self.cam.start()  # start recording images into the camera buffer
        log.info("Acquiring image ... ")
        try:
            if self.setting.calibrated:
                img = self.cam.get_array()  # Get image as numpy array
                roll, pitch, yaw = self.est.pose_from_image(img)  # estimate the head pose from the np array
                if self.offset:
                    self.pose.append([roll-self.offset[0], pitch-self.offset[1], yaw-self.offset[2]])  # subtract offset
                else:
                    log.info("WARNING: Camera not calibrated, head pose might be unreliable ...")
                    self.pose.append([roll, pitch, yaw])
                log.info("Acquired pose!")
        except ValueError:
            print("Could not recognize face, make sure that camera can see the face!")

    def _pause(self, **kwargs):
        """
        Pauses the camera and sets the state to "paused".
        """
        self.cam.stop()

    def _stop(self):
        """
        Closes the camera and cleans up and sets the state to "stopped".
        """
        self.cam.close()  # close camera

    def calibrate(self):
        """
        Calibrates the camera. Initializes the RX81 to access the central loudspeaker. Illuminates the led on ele, azi 0°,
        then acquires the headpose and uses it as the offset. Turns the led off afterwards.
        """
        log.info("Calibrating camera ...")
        expdir = get_config('DEVICE_ROOT')
        self.handle = tdt.Processors()
        self.handle.initialize(proc_list=[[self.setting.processor,
                                           self.setting.processor,
                                           os.path.join(expdir, self.setting.file)]],
                                           connection=self.setting.connection)
        print(f"Initialized {self.setting.processor}{self.setting.index}.")
        self.handle.write(tag='bitmask',
                          value=self.setting.led_spk.digital_channel,
                          processors=self.setting.led_spk.digital_proc)  # illuminate LED
        try:
            roll, pitch, yaw = self.get_pose()  # get head pose
            self.offset = [roll, pitch, yaw]  # use head pose as offset
            self.handle.write(tag='bitmask', value=0, processors=self.setting.led_spk.digital_proc)  # turn off LED
            self.setting.calibrated = True
            log.info("Successfully calibrated camera!")
        except ValueError:
            log.info("Could not see the face, make sure that the camera is seeing the face!")
        if self.setting.calibrated:
            self.handle.halt()

    def snapshot(self, cmap="gray"):
        """
        Args:
            cmap: matplotlib colormap
        """
        log.info("Acquiring snapshot ...")
        image = self.cam.get_array()  # get image as np array
        plt.imshow(image, cmap=cmap)  # show image
        plt.show()

    @staticmethod
    def brighten(image, factor):
        """
        Brightens the image by a factor.
        Args:
            image: image to be brightened, must be in the form of an array.
            factor: factor by which the image gets brightened.

        Returns:
            brightened image array.
        """
        img = Image.fromarray(image)  # transform array to PIL.Image object
        filter = ImageEnhance.Brightness(img)  # create brightness filter
        brightimg = filter.enhance(factor)  # enhance image
        array = np.asarray(brightimg)  # transform back to array
        return array

    @staticmethod
    def sharpen(image, factor):
        """
        Args:
            image: image to be sharpened, must be in the form of an array.
            factor: factor by which the image gets sharpened.

        Returns:
            sharpened image array.
        """
        img = Image.fromarray(image)  # transform array to PIL.Image object
        filter = ImageEnhance.Sharpness(img)  # create sharpness filter
        sharpimg = filter.enhance(factor)  # enhance image
        array = np.asarray(sharpimg)  # transform back to array
        return array


if __name__ == "__main__":
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    log.addHandler(ch)

    cam = ArUcoCam()
    cam.initialize()

    interval = 10
    poses = list()
    azimuth = list()
    elevation = list()

    for trial in range(interval):
        cam.configure()
        cam.start()
        cam.snapshot()
        cam.pause()
        poses.append(cam.setting.pose)

    for azi, ele in poses:
        azimuth.append(azi)
        elevation.append(ele)

    print(f"SD over {interval} trials: \
          azimuth:{np.std(azimuth)}\
          elevation: {np.std(elevation)}")

    # Facial landmark detection logic test
    # see if the logic works
    """
    cam = FlirCam()
    cam.initialize()
    cam.configure()
    cam.start()
    cam.snapshot()
    cam.pause()
    
    # headpose estimation
    import time
    time.sleep(10)
    est = PoseEstimator()
    cam = Camera()
    cam.init()
    cam.start()
    img = cam.get_array()
    cam.stop()
    img = Image.fromarray(img)
    brightness = ImageEnhance.Brightness(img)
    bright = brightness.enhance(6.0)
    array = np.asarray(bright)
    roll, pitch, yaw = est.pose_from_image(array)  # estimate the head pose
    """



