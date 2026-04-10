import argparse
import rasterio
from rasterio.features import shapes
import numpy as np
import cv2
import json
import geopandas as gpd
import matplotlib.pyplot as plt


class AnalisaPlantio:
    """Analisa uma imagem georreferenciada e extrai geometrias e estatísticas do plantio"""

    def __init__(self, tif_path, show_plots=False):
        """
        Inicializa as variáveis, extrai metadados e chama as funções

        :param tif_path: caminho para a imagem georreferenciada
        :param show_plots: se True, mostra os gráficos para análise visual
        """

        self.src = rasterio.open(tif_path)  # Abre a img georreferenciada para leitura

        # Inicialização de variáveis
        self.tif_path = tif_path
        self.show_plots = show_plots
        self.idx = None
        self.binary = None
        self.gdf = None
        self.area_total_ha = None
        self.mudas_total = None
        self.mudas_por_ha = None
        self.homogeneidade = None

        # Extração de metadados ============================================================================
        src = self.src  # Apelido para usar dentro da função
        self.crs = src.crs  # Obtém o Sistema de Referência de Coordenadas (CRS)
        self.transform = src.transform  # Obtém a matriz de transformação que converte pixel para coordenada
        
        res_x, res_y = src.res  # Extrai a resolução espacial (largura/altura do pixel) em unidades do CRS
        self.gsd_area = abs(res_x * res_y)  # Calcula a área real ocupada por um único pixel em m²
        
        gsd = (abs(res_x) + abs(res_y)) / 2  # Ground Sampling Distance (GSD)
        print(f"GSD: {gsd:.4f} m/px")
        
        unit = src.crs.linear_units  # Extrai a unidade do CRS
        print(f"Unidade do CRS: {unit}")
        
        # Extração dos canais RGB ==========================================================================
        self.r = src.read(1).astype('float32')  # Vermelho
        self.g = src.read(2).astype('float32')  # Verde
        self.b = src.read(3).astype('float32')  # Azul

        # Chamando as funções
        self.realiza_contraste()
        self.tratamento_morfologico()
        self.obtem_poligonos()
        self.obtem_estatisticas()
        self.exporta_resultados()

    def realiza_contraste(self):
        """Realiza um contraste na imagem para realçar as mudas"""
        
        # Índice de imagem --> intensidade média
        intensidade = (self.r + self.g + self.b) / 3

        # Normalização (para a escala 0-255)
        self.idx = cv2.normalize(intensidade, None, 0, 255, cv2.NORM_MINMAX).astype('uint8')

        # Inversão (para que as mudas fiquem claras e o restante escuro)
        self.idx = 255 - self.idx

        # Visualização do contraste realizado
        if self.show_plots:
            plt.figure(figsize=(10, 5))
            plt.title("Mapa de contraste")
            plt.imshow(self.idx)
            plt.colorbar()
            plt.show()

    def tratamento_morfologico(self):
        """Realiza binarização e limpeza morfológica"""

        # Binarização da imagem utilizando o método de Otsu
        _, binary = cv2.threshold(self.idx, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bin_copy = binary.copy() # Cópia para comparação visual

        # Operações morfológicas ========================================================
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))  # Kernel 3 x 3
        
        # Abertura (erosão seguida de dilatação) para remover ruídos pequenos do solo
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        self.binary = binary

        # Mais uma iteração de abertura em uma img auxiliar para comparação visual
        bin_aux = cv2.morphologyEx(bin_copy, cv2.MORPH_OPEN, kernel, iterations=2)

        # Visualização do impacto da limpeza morfológica
        if self.show_plots:
            plt.figure(figsize=(30, 5))
            plt.subplot(1, 3, 1); plt.title("Imagem binarizada"); plt.imshow(bin_copy, cmap='gray')
            plt.subplot(1, 3, 2); plt.title("Imagem após abertura (1 iteração)"); plt.imshow(binary, cmap='gray')
            plt.subplot(1, 3, 3); plt.title("Imagem após abertura (2 iterações)"); plt.imshow(bin_aux, cmap='gray')
            plt.show()

    def obtem_poligonos(self):
        """Obtém geometrias para as mudas e realiza ajuste fino"""
        
        # Vetorização =====================================================================================
        results = (
            {'properties': {'raster_val': v}, 'geometry': s}
            for _, (s, v) in enumerate(shapes(self.binary, mask=self.binary > 0, transform=self.transform))
        )
        # A variável results gera dicionários GeoJSON mapeando as mudas
        # Ela é criada pela função shapes do rasterio, que percorre a img agrupando pixels de valor > 0
        # e aplicando a matriz que converte cada pixel em coordenadas geográficas reais
        
        geoms = list(results)  # Transformando em list

        # Convertendo a lista de geometrias em um df do Geopandas
        gdf = gpd.GeoDataFrame.from_features(geoms, crs=self.crs)

        # Filtro de ruído =========================================================================
        gdf['area_m2'] = gdf['geometry'].area  # Incluindo a área de cada muda no df para filtragem
        
        # Filtrando por área (considerando de 0.24m² a 1.6m²)
        gdf = gdf[(gdf['area_m2'] > 0.24) & (gdf['area_m2'] < 1.6)].copy()
        self.gdf = gdf

    def obtem_estatisticas(self):
        """Calcula estatísticas, bem como a homogeneidade do plantio"""
        
        # Estatísticas do resultado ================================================================
        mask = self.src.read_masks(1)  # Lendo os dados ausentes (bordas e fundo da imagem)

        pixels_com_dados = np.count_nonzero(mask)  # Conta apenas os pixels que contêm dado real

        self.area_total_ha = (pixels_com_dados * self.gsd_area) / 10000  # Área total em [ha]
        self.mudas_total = len(self.gdf)                                 # Qtde total de mudas
        self.mudas_por_ha = self.mudas_total / self.area_total_ha        # Mudas por ha
        
        # Métrica de homogeneidade do plantio  =====================================================
        area_std = self.gdf['area_m2'].std()  # Desvio padrão das áreas das mudas
        area_mean = self.gdf['area_m2'].mean()  # Área média de todas as mudas
        
        # Invertemos o CV (1 - CV) para que 1 represente uniformidade perfeita
        cv = area_std / area_mean    # CV --> coeficiente de variação
        self.homogeneidade = 1 - cv  # Homogeneidade --> 1 - CV

    def exporta_resultados(self):
        """Exporta os arquivos GeoJSON e JSON"""

        # Criando os nomes dos arquivos que serão exportados
        final = self.tif_path[self.tif_path.rfind('/') + 1:self.tif_path.rfind('.')]
        geojson_filename = f'output_mudas_{final}.geojson'
        json_filename = f'output_stats_{final}.json'

        # Exportando o df para um arquivo GeoJSON
        self.gdf.to_file(geojson_filename, driver='GeoJSON')

        # Agrupando as estatísticas em um dicionário
        stats = {
            "mudas_total": int(self.mudas_total),
            "area_total_ha": round(float(self.area_total_ha), 2),
            "mudas_por_ha": round(float(self.mudas_por_ha), 2),
            "homogeneidade": round(float(max(0, self.homogeneidade)), 2)
        }
        
        # Salvando o dicionário como arquivo JSON
        with open(json_filename, 'w') as f:
            json.dump(stats, f, indent=4)


def main():

    # Interpretador de argumentos
    parser = argparse.ArgumentParser(description="Analisa uma imagem georreferenciada")

    # Definindo os argumentos
    parser.add_argument("tif_path", help="Caminho para o arquivo .tif de entrada")
    parser.add_argument("--show", action="store_true", help="Mostra os gráficos de análise visual")

    # Pegando os argumentos do terminal
    args = parser.parse_args()

    # Instanciando a classe
    ap = AnalisaPlantio(
        tif_path=args.tif_path,
        show_plots=args.show
    )
    print(f'Programa finalizado: {ap.mudas_total} mudas detectadas.')

if __name__ == '__main__':
    main()
