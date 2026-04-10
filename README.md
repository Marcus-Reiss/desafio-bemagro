# Desafio P&D - BEMAGRO

**Candidato:** Marcus Vinícius Costa Reis

**Vaga:** Desenvolvedor de IA

---

### Sobre a solução

O *script* que foi desenvolvido implementa uma classe que analisa uma imagem georreferenciada e extrai geometrias e estatísticas do plantio.

A classe conta com algumas funções, que dividem o fluxo de trabalho, o qual pode ser resumido nos seguintes pontos:

1. Extração de metadados e canais RGB da imagem
2. Realização de contraste para realçar as mudas de eucalipto
3. Binarização da imagem e operação morfológica de abertura
4. Obtenção de polígonos e realização de ajuste fino com base na área de cada muda
5. Cálculo de estatísticas e homogeneidade do plantio
6. Criação e exportação dos arquivos GeoJSON e JSON

### Execução do *script*

Para executar o *script*, siga os passos abaixo:

1. Clone o presente repositório:

```
git clone https://github.com/Marcus-Reiss/desafio-bemagro.git
```

2. Na raiz do repositório, execute o programa com o comando abaixo. O argumento `tif_path` deve receber o caminho para a imagem. No presente caso, ele deve ser `'dados/sample1.tif'` ou `'dados/sample2.tif'`.

```
python3 analisa_plantio.py tif_path
```

3. Caso deseje visualizar os gráficos que foram usados ao longo do programa para validação visual, adicione a flag `--show` ao comando anterior:

```
python3 analisa_plantio.py tif_path --show
```

Ao término da execução, algumas mensagens serão printadas no terminal e os arquivos GeoJSON e JSON serão salvos na raiz do repositório.
