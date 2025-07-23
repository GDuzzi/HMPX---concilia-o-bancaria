
from abc import ABC, abstractmethod
import unicodedata

class ParserBase(ABC):
    """
    Interface abstrata para parsers de empresas.
    Define os métodos mínimos que qualquer parser deve implementar.
    """

    @staticmethod
    def normalize_text(text):
        """Normaliza texto para facilitar comparações."""
        if not isinstance(text, str):
            text = str(text)
        return " ".join(
            unicodedata.normalize("NFD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
            .split()
        )

    @abstractmethod
    def parse_valor(self, valor):
        """Converte o valor para número decimal padronizado."""
        pass

    @abstractmethod
    def importar_arquivo(self, arquivos: list[str]) -> dict:
        """Importa e processa os arquivos da empresa."""
        pass
