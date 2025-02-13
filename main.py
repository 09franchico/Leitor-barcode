
from qreader import QReader
import sys
import cv2
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QFileDialog, QSlider,QLabel,QGridLayout
from PySide6.QtCore import QThread, Signal, Qt
import qdarktheme
import zxingcpp


class VideoThread(QThread):
    frame_signal = Signal(np.ndarray) 

    def __init__(self,parent):
        super().__init__()
        self.parent_main = parent
        self.running = True

    def run(self):

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Erro: Não foi possível abrir a câmera.")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 2592)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1944)
        self.cap.set(cv2.CAP_PROP_FPS, 200)

        while self.running:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = np.flipud(frame)
                self.parent_main.img1a.setImage(frame.astype(np.float32), levels=(0, 255))
                self.frame_signal.emit(frame)  

    def stop(self):
        self.running = False
        self.cap.release()


class QreaderBarCodeThread(QThread):

    result_brcode_qreader = Signal(str)  
    result_barcode = Signal(str)

    def __init__(self,rois_regions,qreader):
        super().__init__()
        self.rois_regions = rois_regions
        self.qreader = qreader

    def run(self):
         for i, roi_region in enumerate(self.rois_regions):
            roi_region_item = np.array(roi_region, dtype=np.uint8)
            codebarras_text = self.detect_barcodes(roi_region_item)
            decoded_text = self.qreader.detect_and_decode(roi_region_item)

            self.result_barcode.emit(f"{codebarras_text}")
            self.result_brcode_qreader.emit(f"{decoded_text}") 
           
    def detect_barcodes(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        results = zxingcpp.read_barcodes(gray)
        code_barras = ""
        for result in results:    
            code_barras = result.text
        if len(results) == 0:
            return None
        return code_barras




class ROIExamples(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DgbQRCode")

        self.qreader = QReader(weights_folder="tmp")
        
        #--------------------------
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        #--------------------------
        self.layout_grid_principal = QGridLayout()
        self.central_widget.setLayout(self.layout_grid_principal)
        
        #--------------------------
        pg.setConfigOptions(imageAxisOrder="row-major")
        self.create_gui()
        
        #--------------------------
        self.video_thread = None
        self.thread_barcode_qreader = None

    def create_gui(self):
        # --------------------------
        self.graphics_layout_widget = pg.GraphicsLayoutWidget()
        self.w1 = self.graphics_layout_widget.addLayout(row=0, col=0)
        self.v1a = self.w1.addViewBox(row=1, col=0)
        self.v1a.setMouseEnabled(x=True, y=True)
        self.v1a.enableAutoRange()
        self.img1a = pg.ImageItem()
        self.v1a.addItem(self.img1a)

        self.layout_grid_principal.addWidget(self.graphics_layout_widget, 0, 0, 1, 3)

        # --------------------------
        self.text_result_qr = QLabel("RESULTADO:")
        self.layout_grid_principal.addWidget(self.text_result_qr, 3, 0, 1, 3)

        self.open_camera = QPushButton("ABRIR CAMERA")
        self.open_camera.clicked.connect(self.open_camera_qr)
        self.layout_grid_principal.addWidget(self.open_camera, 1, 0)

        self.stop_camera = QPushButton("PARAR CAMERA")
        self.stop_camera.clicked.connect(self.stop_camera_qr)
        self.layout_grid_principal.addWidget(self.stop_camera, 1, 1)

        self.add_roi_button = QPushButton("AREA DE INTERESSE")
        self.add_roi_button.clicked.connect(self.add_new_roi)
        self.layout_grid_principal.addWidget(self.add_roi_button, 1, 2)

        self.save_roi_button = QPushButton("SALVAR AREAS")
        self.save_roi_button.clicked.connect(self.save_rois)
        self.layout_grid_principal.addWidget(self.save_roi_button, 2, 0)

        self.reset_zoom_button = QPushButton("RESETAR ZOOM")
        self.reset_zoom_button.clicked.connect(self.reset_zoom)
        self.layout_grid_principal.addWidget(self.reset_zoom_button, 2, 1)

        self.read_qr_button = QPushButton("LER QRCODES")
        self.read_qr_button.clicked.connect(self.read_qr_code)
        self.layout_grid_principal.addWidget(self.read_qr_button, 2, 2)

        self.focus_slider = QSlider(Qt.Horizontal)
        self.focus_slider.setMinimum(0)
        self.focus_slider.setMaximum(1000)
        self.focus_slider.setValue(0)
        self.focus_slider.setTickInterval(5)
        self.focus_slider.setTickPosition(QSlider.TicksBelow)
        self.focus_slider.valueChanged.connect(self.set_focus)
        self.layout_grid_principal.addWidget(self.focus_slider, 4, 0, 1, 3)

        self.brilho_slider = QSlider(Qt.Horizontal)
        self.brilho_slider.setMinimum(-100)
        self.brilho_slider.setMaximum(100)
        self.brilho_slider.setValue(0)
        self.brilho_slider.setTickInterval(5)
        self.brilho_slider.setTickPosition(QSlider.TicksBelow)
        self.brilho_slider.valueChanged.connect(self.set_brilho)
        self.layout_grid_principal.addWidget(self.brilho_slider, 5, 0, 1, 3)

        self.rois = []
        
        
    def stop_camera_qr(self):
        if self.video_thread is not None:
            self.video_thread.stop()
        
    def open_camera_qr(self):
        if self.video_thread  and self.video_thread.isRunning():
            print("Thread ja estar em execuaco")
            return
        self.video_thread = VideoThread(self)
        self.video_thread.frame_signal.connect(self.update_frame)
        self.video_thread.start()
        

    def add_new_roi(self):
        new_roi = pg.RectROI([20, 20], [100, 100], pen=(0, 9))
        new_roi.addRotateHandle([1, 0], [0.5, 0.5])
        self.v1a.addItem(new_roi)
        self.rois.append(new_roi)

    def update_frame(self, frame):
        self.current_frame = frame


    def save_rois(self):
        if not hasattr(self, "current_frame"):
            print("Erro: Nenhum frame capturado.")
            return

        save_path = QFileDialog.getExistingDirectory(self, "Escolha a pasta para salvar as ROIs")
        if not save_path:
            return

        for i, roi in enumerate(self.rois):
            roi_region = roi.getArrayRegion(self.current_frame, self.img1a)
            if roi_region is not None:
                roi_region = np.array(roi_region, dtype=np.uint8)
                if roi_region.max() <= 1.0:
                    roi_region = (roi_region * 255).astype(np.uint8)
                roi_region = cv2.cvtColor(roi_region, cv2.COLOR_RGB2BGR)
                file_path = f"{save_path}/roi_{i}.png"
                cv2.imwrite(file_path, roi_region)
                print(f"ROI {i} salva em {file_path}")

    def reset_zoom(self):
        self.v1a.autoRange()

    def read_qr_code(self):
        if not hasattr(self, "current_frame"):
            print("Erro: Nenhuma imagem capturada para leitura do QR Code.")
            return

        if not self.rois:
            print("Erro: Nenhuma ROI foi adicionada.")
            return
        
        if self.thread_barcode_qreader  and self.thread_barcode_qreader .isRunning():
            print("Thread anterior ainda está ativa. Aguardando término.")
            return
        
        rois_regions = []
        
        for i, roi in enumerate(self.rois):
            roi_region = roi.getArrayRegion(self.current_frame, self.img1a)
            if roi_region is not None:
                roi_region = np.array(roi_region, dtype=np.uint8)
                rois_regions.append(roi_region)
            else:
                print(f"Falha ao extrair a região da ROI {i}.")


        self.thread_barcode_qreader = QreaderBarCodeThread(
                                                      rois_regions,
                                                      self.qreader)
        self.thread_barcode_qreader.result_brcode_qreader.connect(self.result_barcode_qreader)
        self.thread_barcode_qreader.result_barcode.connect(self.result_barcode)
        self.thread_barcode_qreader.start()

    def result_barcode(self,value):
        print("RESULTADO BARCODE : ",value)

    def result_barcode_qreader(self,value):
        print("RESULTADO QRCODE : ",value)
        self.text_result_qr.setText(f"RESULTADO : {value}")


    def set_focus(self, value):
        if self.video_thread.cap is not None and self.video_thread.cap.isOpened():
            focus_property = cv2.CAP_PROP_FOCUS
            if self.video_thread.cap.get(focus_property) != -1:
                self.video_thread.cap.set(focus_property, value)
                print(f"Foco ajustado para: {value}")
            else:
                print("Esta câmera não suporta ajuste de foco.")

    def set_brilho(self, value):
        if self.video_thread.cap is not None and self.video_thread.cap.isOpened():
            brightness_supported = self.video_thread.cap.get(cv2.CAP_PROP_BRIGHTNESS)

            if brightness_supported == -1:
                print("Ajuste de brilho não suportado por esta câmera.")
                return

            self.video_thread.cap.set(cv2.CAP_PROP_BRIGHTNESS, value)
            print(f"Brilho ajustado para: {value}")

    def closeEvent(self, event):
        if self.video_thread is not None:
            self.video_thread.stop()


if __name__ == "__main__":
    app = QApplication([])
    qdarktheme.setup_theme("dark")
    window = ROIExamples()
    window.resize(500, 500)
    window.show()
    app.exec()



    