class ImageProcessor:
    def __init__(self):
        self.original_gray = None   # imagem original carregada
        self.image = None           # imagem processada
        self.alpha = 1.0            # contraste
        self.beta = 0               # brilho
        self.zoom = 1.0             # zoom
        self.inverted = False       # inversão de cores

    def load_image(self, path):
        import cv2
        # Carregar a imagem em escala de cinza
        self.original_gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        self.image = self.original_gray.copy()  # copiar para aplicar ajustes

    def apply_adjustments(self):
        if self.original_gray is None:
            return None
        import cv2
        import numpy as np
        # aplicar brilho e contraste
        adjusted = cv2.convertScaleAbs(self.original_gray, alpha=self.alpha, beta=self.beta)
        # inverter cores
        if self.inverted:
            adjusted = cv2.bitwise_not(adjusted)
        # aplicar zoom
        if self.zoom != 1.0:
            h, w = adjusted.shape[:2]
            new_size = (int(w*self.zoom), int(h*self.zoom))
            adjusted = cv2.resize(adjusted, new_size, interpolation=cv2.INTER_LINEAR)
        self.image = adjusted
        return adjusted

    # --- Setters ---
    def set_brightness(self, val):
        self.beta = val

    def set_contrast(self, val):
        self.alpha = val

    def set_zoom(self, val):
        self.zoom = val

    # --- Invert ---
    def toggle_invert(self):
        self.inverted = not self.inverted

    def set_invert(self, value: bool):
        """
        Aplica o estado de inversão exatamente como especificado.
        """
        if self.inverted != value:
            self.toggle_invert()
