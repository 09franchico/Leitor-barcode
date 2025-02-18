from qreader import QReader
import sys
import cv2
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QFileDialog, QSlider,QLabel,QGridLayout
from PySide6.QtCore import QThread, Signal, Qt,QTimer
import qdarktheme
import zxingcpp



class QreaderBarCodeThread(QThread):

    result_brcode_qreader = Signal(dict)
    
    def __init__(self,rois_regions,qreader):
        super().__init__()
        self.rois_regions = rois_regions
        self.qreader = qreader

    def run(self):
        
        self.sr = cv2.dnn_superres.DnnSuperResImpl_create()
        path = "FSRCNN_x4.pb"
        self.sr.readModel(path)
        self.sr.setModel("fsrcnn", 4)  

        dados = {
             "qrcode" :[],
             "barcode":[]
         }
         
        for i, roi_region in enumerate(self.rois_regions):
            roi_region_item = np.array(roi_region, dtype=np.uint8)
            
            roi_region_item = self.sr.upsample(roi_region_item)  # Aumenta a qualidade
            
            decoded_text = self.qreader.detect_and_decode(roi_region_item)
            if decoded_text:
                dados["qrcode"].append(decoded_text[0])
            else:
                codebarras_text = self.detect_barcodes(roi_region_item)
                if codebarras_text:
                    dados["barcode"].append(codebarras_text)
            
            
        self.result_brcode_qreader.emit(dados)
           
    def detect_barcodes(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        results = zxingcpp.read_barcodes(gray)
        code_barras = ""
        for result in results:    
            code_barras = result.text
        if len(results) == 0:
            return None
        return code_barras



class VideoThread(QThread):
    frame_signal = Signal(np.ndarray) 

    def __init__(self,id_camera:int = 0, w:int = 2592, h:int=1944,fps:int = 60):
        super().__init__()
        self.id_camera = id_camera
        self.w = w
        self.h = h
        self.fps = fps
        self.running = True

    def run(self):

        self.cap = cv2.VideoCapture(self.id_camera)
        
        if not self.cap.isOpened():
            print("Erro: Não foi possível abrir a câmera.")
            return
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        while self.running:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = np.flipud(frame)
                self.frame_signal.emit(frame)  

    def stop(self):
        self.running = False
        self.cap.release()




class PlayThread(QThread):
    
    resultado = Signal(np.ndarray) 

    def __init__(self,parent_view, qreader):
        
        super().__init__()
        
        self.parent_view = parent_view
        self.qreader = qreader
        self.running = True
        
        
    def run(self):
        
        self.sr = cv2.dnn_superres.DnnSuperResImpl_create()
        path = "FSRCNN-small_x4.pb"
        self.sr.readModel(path)
        self.sr.setModel("fsrcnn", 4)

        
        while self.running:
            
        
            #busca os dados da tela
            frame_atual = self.parent_view.current_frame.copy()
            ima1a_atual = self.parent_view.img1a
            rois = self.parent_view.rois
            
            dados = {
               "qrcode" :[],
               "barcode":[]
            }
            
            
            for i, roi in enumerate(rois):
                
                roi_region = roi.getArrayRegion(frame_atual, ima1a_atual)
                
                if roi_region is not None:
                    
                    roi_region_item = np.array(roi_region, dtype=np.uint8)
                    roi_region_item = self.sr.upsample(roi_region_item) 
                    
                    #decode
                    # decoded_text = self.qreader.detect_and_decode(roi_region_item)
                    # if decoded_text:
                    #     dados["qrcode"].append(decoded_text[0])
                    # else:
                    codebarras_text = self.detect_barcodes(roi_region_item)
                    if codebarras_text:
                        dados["barcode"].append(codebarras_text)
                    
                    
                    
                else:
                    print(f"Falha ao extrair a região da ROI {i}.")
            
            
            
            if self.running == False:
                    break
            
            self.resultado.emit(dados)
            
            
    def detect_barcodes(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        results = zxingcpp.read_barcodes(gray)
        code_barras = ""
        for result in results:    
            code_barras = result.text
        if len(results) == 0:
            return None
        return code_barras
            
            
                
    def stop(self):
        self.running = False


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
        self.play_thread = None
        self.thread_barcode_qreader = None

    def create_gui(self):
        # --------------------------
        self.graphics_layout_widget = pg.GraphicsLayoutWidget()
        self.w1 = self.graphics_layout_widget.addLayout(row=0, col=0)
        self.v1a = self.w1.addViewBox(row=1, col=0)
        
        self.v1a.setDefaultPadding(0)
        self.v1a.setMouseEnabled(x=True, y=True)
        self.v1a.enableAutoRange()
        
        
        self.img1a = pg.ImageItem()
        self.v1a.addItem(self.img1a)
        

        self.layout_grid_principal.addWidget(self.graphics_layout_widget, 0, 0, 1, 5)

        # --------------------------
        self.text_result_qr = QLabel("RESULTADO:")
        self.layout_grid_principal.addWidget(self.text_result_qr, 3, 0, 1, 5)

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
        
        self.play_button = QPushButton("PLAY")
        self.play_button.clicked.connect(self.play)
        self.layout_grid_principal.addWidget(self.play_button, 2, 3)
        
        self.stop_button = QPushButton("STOP")
        self.stop_button.clicked.connect(self.stop)
        self.layout_grid_principal.addWidget(self.stop_button, 2, 4)

        # Sliders com Labels
        self.focus_label = QLabel("Foco")
        self.layout_grid_principal.addWidget(self.focus_label, 4, 0)
        self.focus_slider = QSlider(Qt.Horizontal)
        self.focus_slider.setMinimum(0)
        self.focus_slider.setMaximum(1000)
        self.focus_slider.setValue(0)
        self.focus_slider.setTickInterval(5)
        self.focus_slider.setTickPosition(QSlider.TicksBelow)
        self.focus_slider.valueChanged.connect(self.set_focus)
        self.layout_grid_principal.addWidget(self.focus_slider, 4, 1, 1, 2)

        self.brilho_label = QLabel("Brilho")
        self.layout_grid_principal.addWidget(self.brilho_label, 5, 0)
        self.brilho_slider = QSlider(Qt.Horizontal)
        self.brilho_slider.setMinimum(-100)
        self.brilho_slider.setMaximum(100)
        self.brilho_slider.setValue(0)
        self.brilho_slider.setTickInterval(5)
        self.brilho_slider.setTickPosition(QSlider.TicksBelow)
        self.brilho_slider.valueChanged.connect(self.set_brilho)
        self.layout_grid_principal.addWidget(self.brilho_slider, 5, 1, 1, 2)

        self.contraste_label = QLabel("Contraste")
        self.layout_grid_principal.addWidget(self.contraste_label, 6, 0)
        self.contraste_slider = QSlider(Qt.Horizontal)
        self.contraste_slider.setMinimum(-100)
        self.contraste_slider.setMaximum(100)
        self.contraste_slider.setValue(0)
        self.contraste_slider.setTickInterval(5)
        self.contraste_slider.setTickPosition(QSlider.TicksBelow)
        self.contraste_slider.valueChanged.connect(self.set_contraste)
        self.layout_grid_principal.addWidget(self.contraste_slider, 6, 1, 1, 2)

        self.saturation_label = QLabel("Saturação")
        self.layout_grid_principal.addWidget(self.saturation_label, 7, 0)
        self.saturation_slider = QSlider(Qt.Horizontal)
        self.saturation_slider.setMinimum(-100)
        self.saturation_slider.setMaximum(100)
        self.saturation_slider.setValue(0)
        self.saturation_slider.setTickInterval(5)
        self.saturation_slider.setTickPosition(QSlider.TicksBelow)
        self.saturation_slider.valueChanged.connect(self.set_saturation)
        self.layout_grid_principal.addWidget(self.saturation_slider, 7, 1, 1, 2)

    
        self.rois = []
        
        
    def stop_camera_qr(self):
        if self.video_thread is not None:
            self.video_thread.stop()
        
    def open_camera_qr(self):
        
        if self.video_thread  and self.video_thread.isRunning():
            print("Thread ja estar em execuaco")
            return
        
        self.video_thread = VideoThread(id_camera=0,w=3840,h=3104,fps=100)
        self.video_thread.frame_signal.connect(self.update_frame)
        self.video_thread.start()
                
        
    def add_new_roi(self):
        view_range = self.v1a.viewRange()
        center_x = (view_range[0][0] + view_range[0][1]) / 2
        center_y = (view_range[1][0] + view_range[1][1]) / 2
        roi_width, roi_height = 100, 100
        new_roi = pg.RectROI([center_x - roi_width / 2, center_y - roi_height / 2], [roi_width, roi_height], pen=(0, 9))
        new_roi.addRotateHandle([1, 0], [0.5, 0.5])
        self.v1a.addItem(new_roi)
        self.rois.append(new_roi)
    
        
    def update_frame(self, frame):
        self.current_frame = frame    
        QTimer.singleShot(0, lambda: self.img1a.setImage(frame, autoLevels=False))


    def save_rois(self):
        
        if not self.rois:
            print("Erro: Nenhuma ROI foi adicionada.")
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
        
        
    def play(self):
        if not self.rois:
            print("Erro: Nenhuma ROI foi adicionada.")
            return
        
        if self.play_thread  and self.play_thread.isRunning():
            print("Thread anterior ainda está ativa. Aguardando término.")
            return
    
        self.text_result_qr.setText("Executando play...")
        self.play_thread = PlayThread(parent_view=self,
                                      qreader=self.qreader)
        self.play_thread.resultado.connect(self.result_play)
        self.play_thread.start()
        
        
    def result_play(self,value):
        self.text_result_qr.setText(f"EM EXECUCÃO : QRCODE : {value.get('qrcode')}           BARCODE : {value.get('barcode')}")
        print(value)
        
        
    def stop(self):
        self.text_result_qr.setText("PARADA REALIZADA !")
        self.play_thread.stop()

    def read_qr_code(self):
       
        if not self.rois:
            print("Erro: Nenhuma ROI foi adicionada.")
            return
        
        if self.thread_barcode_qreader  and self.thread_barcode_qreader .isRunning():
            print("Thread anterior ainda está ativa. Aguardando término.")
            return
        
  
        rois_regions = []
        
        frame_atual = self.current_frame.copy()
        ima1a_atual = self.img1a
        
        for i, roi in enumerate(self.rois):
            roi_region = roi.getArrayRegion(frame_atual, ima1a_atual)
            if roi_region is not None:
                roi_region = np.array(roi_region, dtype=np.uint8)
                rois_regions.append(roi_region)
            else:
                print(f"Falha ao extrair a região da ROI {i}.")
                
        self.text_result_qr.setText("Realizando leitura...")

        self.thread_barcode_qreader = QreaderBarCodeThread(
                                                      rois_regions,
                                                      self.qreader)
        self.thread_barcode_qreader.result_brcode_qreader.connect(self.result_barcode_qreader)
        self.thread_barcode_qreader.start()


    def result_barcode_qreader(self,value):
        self.text_result_qr.setText(f"QRCODE : {value.get('qrcode')}           BARCODE : {value.get('barcode')}")
        print(value)

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
            
    def set_contraste(self,value):
        if self.video_thread.cap is not None and self.video_thread.cap.isOpened():
            brightness_supported = self.video_thread.cap.get(cv2.CAP_PROP_CONTRAST)

            if brightness_supported == -1:
                print("Ajuste de Contraste não suportado por esta câmera.")
                return

            self.video_thread.cap.set(cv2.CAP_PROP_CONTRAST, value)
            print(f"Contraste  ajustado para: {value}")
                        
    def set_saturation(self,value):
        
        if self.video_thread.cap is not None and self.video_thread.cap.isOpened():
            brightness_supported = self.video_thread.cap.get(cv2.CAP_PROP_SATURATION)

            if brightness_supported == -1:
                print("Ajuste de SATURACAO não suportado por esta câmera.")
                return

            self.video_thread.cap.set(cv2.CAP_PROP_SATURATION, value)
            print(f"SATURACAO ajustado para: {value}")
        

    def closeEvent(self, event):
        if self.video_thread is not None:
            self.video_thread.stop()
           
            
    
if __name__ == "__main__":
    app = QApplication([])
    qdarktheme.setup_theme("dark")
    window = ROIExamples()
    window.resize(700, 700)
    window.show()
    app.exec()