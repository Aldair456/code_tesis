import unicodedata
import re
import numpy as np
from collections import Counter
from typing import Dict, List, Optional, Union, Set, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class GenericSimilarityClassifier:
    """
    Clasificador genérico de documentos utilizando similitud del coseno.
    Altamente configurable para diferentes dominios y tipos de clasificación.
    """

    def __init__(self,
                 similarity_threshold: float = 0.3,
                 language: str = 'spanish',
                 default_not_detected_label: str = 'NOT_DETECTED'):
        """
        Inicializa el clasificador genérico.

        Args:
            similarity_threshold (float): Umbral mínimo de similitud para clasificación
            language (str): Idioma para stopwords ('spanish', 'english')
            default_not_detected_label (str): Etiqueta cuando no se detecta nada
        """
        self.similarity_threshold = similarity_threshold
        self.default_not_detected_label = default_not_detected_label

        # Cache de plantillas
        self._templates_cache = {}

        # Configuración de clasificación
        self._classification_mapping = {}  # template_name -> classification_label
        self._combination_rules = {}  # tuple(labels) -> combined_label
        self._multiple_detection_strategy = 'combine'  # 'combine', 'highest', 'first', 'all'

        # Configuración de procesamiento
        self.weighted_keywords = {}
        self._stopwords = self._get_stopwords(language)

    def _get_stopwords(self, language: str) -> Set[str]:
        """Obtiene stopwords según el idioma."""
        stopwords_dict = {
            'spanish': {
                'a', 'al', 'algo', 'algunas', 'algunos', 'ante', 'antes', 'aquel', 'aquellas',
                'aquellos', 'aqui', 'asi', 'aunque', 'cada', 'como', 'con', 'contra', 'cual',
                'cuando', 'de', 'del', 'desde', 'donde', 'durante', 'e', 'el', 'ella', 'ellas',
                'ellos', 'en', 'entre', 'era', 'erais', 'eran', 'eras', 'eres', 'es', 'esa',
                'esas', 'ese', 'esos', 'esta', 'estaba', 'estabais', 'estaban', 'estabas',
                'estad', 'estada', 'estadas', 'estado', 'estados', 'estais', 'estamos', 'estan',
                'estando', 'estar', 'estara', 'estaran', 'estaras', 'estare', 'estareis',
                'estaremos', 'estaria', 'estariais', 'estariamos', 'estarian', 'estarias',
                'estas', 'este', 'estos', 'fui', 'fue', 'fuimos', 'fueron', 'fuese', 'fuesen',
                'fuiste', 'fuisteis', 'ha', 'habeis', 'habia', 'habiais', 'habian', 'habias',
                'habida', 'habidas', 'habido', 'habidos', 'habiendo', 'habra', 'habran',
                'habras', 'habre', 'habreis', 'habremos', 'habria', 'habriais', 'habriamos',
                'habrian', 'habrias', 'han', 'has', 'hasta', 'hay', 'haya', 'hayais', 'hayan',
                'hayas', 'he', 'hemos', 'hube', 'hubiera', 'hubieran', 'hubieras', 'hubieron',
                'hubiese', 'hubiesen', 'hubieses', 'hubimos', 'hubiste', 'hubisteis', 'hubo',
                'la', 'las', 'le', 'les', 'lo', 'los', 'mas', 'me', 'mi', 'mia', 'mias', 'mio',
                'mios', 'mis', 'mucho', 'muchos', 'muy', 'nada', 'ni', 'no', 'nos', 'nosotras',
                'nosotros', 'nuestra', 'nuestras', 'nuestro', 'nuestros', 'o', 'os', 'otra',
                'otras', 'otro', 'otros', 'para', 'pero', 'poco', 'por', 'porque', 'que',
                'quien', 'quienes', 'se', 'sea', 'seais', 'seamos', 'sean', 'seas', 'sera',
                'seran', 'seras', 'sere', 'sereis', 'seremos', 'seria', 'seriais', 'seriamos',
                'serian', 'serias', 'si', 'sido', 'siendo', 'sin', 'sobre', 'sois', 'somos',
                'son', 'soy', 'su', 'sus', 'suya', 'suyas', 'suyo', 'suyos', 'tambien', 'tanto',
                'te', 'tendra', 'tendran', 'tendras', 'tendre', 'tendreis', 'tendremos',
                'tendria', 'tendriais', 'tendriamos', 'tendrian', 'tendrias', 'tened', 'teneis',
                'tenemos', 'tener', 'tenga', 'tengais', 'tengamos', 'tengan', 'tengas', 'tengo',
                'tenia', 'teniais', 'teniamos', 'tenian', 'tenias', 'tenida', 'tenidas', 'tenido',
                'tenidos', 'teniendo', 'ti', 'tiene', 'tienen', 'tienes', 'todo', 'todos', 'tu',
                'tus', 'tuve', 'tuviera', 'tuvieran', 'tuvieras', 'tuvieron', 'tuviese',
                'tuviesen', 'tuvieses', 'tuvimos', 'tuviste', 'tuvisteis', 'tuvo', 'tuya',
                'tuyas', 'tuyo', 'tuyos', 'un', 'una', 'uno', 'unos', 'vosotras', 'vosotros',
                'vuestra', 'vuestras', 'vuestro', 'vuestros', 'y', 'ya', 'yo'
            },
            'english': {
                'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he',
                'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'were',
                'will', 'with', 'the', 'this', 'but', 'they', 'have', 'had', 'what', 'said',
                'each', 'which', 'she', 'do', 'how', 'their', 'if', 'up', 'out', 'many', 'then',
                'them', 'these', 'so', 'some', 'her', 'would', 'make', 'like', 'into', 'him',
                'time', 'two', 'more', 'go', 'no', 'way', 'could', 'my', 'than', 'first',
                'been', 'call', 'who', 'oil', 'its', 'now', 'find', 'long', 'down', 'day',
                'did', 'get', 'come', 'made', 'may', 'part'
            }
        }
        return stopwords_dict.get(language, stopwords_dict['english'])

    # CONFIGURACIÓN DE CLASIFICACIÓN

    def configure_classification(self,
                                 template_mapping: Dict[str, str],
                                 combination_rules: Optional[Dict[Tuple[str, ...], str]] = None,
                                 multiple_detection_strategy: str = 'combine') -> None:
        """
        Configura el sistema de clasificación.

        Args:
            template_mapping (Dict[str, str]): Mapeo de nombre_plantilla -> etiqueta_clasificacion
                Ejemplo: {'balance_general': 'BS', 'estado_resultados': 'PL'}
            combination_rules (Optional[Dict[Tuple[str, ...], str]]): Reglas para combinar detecciones
                Ejemplo: {('BS', 'PL'): 'ESTADOS_FINANCIEROS', ('DOC1', 'DOC2', 'DOC3'): 'MULTIPLE'}
            multiple_detection_strategy (str): Estrategia cuando se detectan múltiples tipos
                - 'combine': Usa combination_rules o crea etiqueta combinada
                - 'highest': Retorna el de mayor similitud
                - 'first': Retorna el primero detectado
                - 'all': Retorna lista con todos los detectados
        """
        self._classification_mapping = template_mapping
        self._combination_rules = combination_rules or {}
        self._multiple_detection_strategy = multiple_detection_strategy

    def add_template(self, name: str, template: str, classification_label: str) -> None:
        """
        Agrega una plantilla individual con su etiqueta de clasificación.

        Args:
            name (str): Nombre identificador de la plantilla
            template (str): Contenido de la plantilla
            classification_label (str): Etiqueta de clasificación para esta plantilla
        """
        self._templates_cache[name] = template
        self._classification_mapping[name] = classification_label

    def set_templates(self, templates: Dict[str, str]) -> None:
        """
        Establece múltiples plantillas. Requiere configuración previa de mapeo.

        Args:
            templates (Dict[str, str]): Diccionario con plantillas por nombre
        """
        self._templates_cache = templates

    # CONFIGURACIÓN DE PROCESAMIENTO

    def set_weighted_keywords(self, keywords: Dict[str, int]) -> None:
        """
        Establece palabras clave ponderadas para amplificación.

        Args:
            keywords (Dict[str, int]): Diccionario con palabras clave y sus pesos
        """
        self.weighted_keywords = keywords

    def set_similarity_threshold(self, threshold: float) -> None:
        """Establece el umbral de similitud."""
        self.similarity_threshold = threshold

    # MÉTODOS DE PROCESAMIENTO (sin cambios significativos)

    def generate_ngrams(self, words: List[str], n: int) -> List[tuple]:
        """Genera n-gramas de una lista de palabras."""
        if len(words) < n:
            return []
        return [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]

    def clean_text(self, text: str) -> str:
        """Limpia el texto normalizando y eliminando stopwords."""
        # Normalización Unicode
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        text = text.lower()

        # Eliminación de caracteres especiales
        text = re.sub(r'[^a-zA-ZáéíóúñÑ\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Eliminación de stopwords
        words = text.split()
        words = [word for word in words if word not in self._stopwords]

        return ' '.join(words)

    def amplify_keywords(self, text: str, weighted_words: Optional[Dict[str, int]] = None) -> str:
        """Amplifica palabras clave según su ponderación."""
        if weighted_words is None:
            weighted_words = self.weighted_keywords

        words = text.split()
        amplified = words.copy()

        for word, weight in weighted_words.items():
            if word in words:
                amplified.extend([word] * ((weight - 1) * words.count(word)))

        return ' '.join(amplified)

    def calculate_cosine_similarity(self, text1: str, text2: str) -> float:
        """Calcula la similitud del coseno entre dos textos usando n-gramas."""
        words1 = text1.split()
        words2 = text2.split()

        # Crear n-gramas (unigramas y bigramas)
        ngrams1 = self.generate_ngrams(words1, 1) + self.generate_ngrams(words1, 2)
        ngrams2 = self.generate_ngrams(words2, 1) + self.generate_ngrams(words2, 2)

        # Contar frecuencia de n-gramas
        counter1 = Counter(ngrams1)
        counter2 = Counter(ngrams2)

        # Crear vectores
        all_ngrams = set(counter1.keys()) | set(counter2.keys())
        vector1 = np.array([counter1.get(ngram, 0) for ngram in all_ngrams])
        vector2 = np.array([counter2.get(ngram, 0) for ngram in all_ngrams])

        # Calcular similitud del coseno
        dot_product = np.dot(vector1, vector2)
        norm1 = np.linalg.norm(vector1)
        norm2 = np.linalg.norm(vector2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    # MÉTODO PRINCIPAL DE CLASIFICACIÓN

    def classify_document(self,
                          raw_text: str,
                          custom_templates: Optional[Dict[str, str]] = None,
                          custom_mapping: Optional[Dict[str, str]] = None) -> Union[str, List[str]]:
        """
        Clasifica un documento por similitud con plantillas configuradas.

        Args:
            raw_text (str): Texto crudo del documento
            custom_templates (Optional[Dict[str, str]]): Plantillas personalizadas para esta clasificación
            custom_mapping (Optional[Dict[str, str]]): Mapeo personalizado para esta clasificación

        Returns:
            Union[str, List[str]]: Clasificación del documento o lista de clasificaciones
        """
        if not raw_text or not raw_text.strip():
            logger.warning("Texto vacío proporcionado.")
            return self.default_not_detected_label

        # Determinar plantillas y mapeo a usar
        templates = custom_templates if custom_templates else self._templates_cache
        mapping = custom_mapping if custom_mapping else self._classification_mapping

        if not templates:
            logger.warning("No hay plantillas configuradas.")
            return self.default_not_detected_label

        if not mapping:
            logger.warning("No hay mapeo de clasificación configurado.")
            return self.default_not_detected_label

        # Procesar texto
        clean_text = self.clean_text(raw_text)
        amplified_text = self.amplify_keywords(clean_text)

        # Procesar plantillas
        amplified_templates = {
            name: self.amplify_keywords(self.clean_text(template))
            for name, template in templates.items()
            if name in mapping  # Solo procesar plantillas que tienen mapeo
        }

        # Calcular similitudes
        similarities = {}
        for name, template_text in amplified_templates.items():
            similarity = self.calculate_cosine_similarity(amplified_text, template_text)
            similarities[name] = similarity

        # Log de resultados
        logger.info("Similitudes calculadas:")
        for name, score in sorted(similarities.items(), key=lambda x: x[1], reverse=True):
            classification = mapping.get(name, 'UNKNOWN')
            logger.info(f"{name} -> {classification}: {score:.4f}")

        # Determinar detecciones que superan el umbral
        detected_templates = {
            name: score
            for name, score in similarities.items()
            if score >= self.similarity_threshold
        }

        if not detected_templates:
            return self.default_not_detected_label

        # Convertir a etiquetas de clasificación
        detected_labels = [mapping[name] for name in detected_templates.keys()]
        unique_labels = list(dict.fromkeys(detected_labels))  # Mantener orden, eliminar duplicados

        return self._resolve_multiple_detections(unique_labels, detected_templates, mapping)

    def _resolve_multiple_detections(self,
                                     detected_labels: List[str],
                                     detected_templates: Dict[str, float],
                                     mapping: Dict[str, str]) -> Union[str, List[str]]:
        """Resuelve múltiples detecciones según la estrategia configurada."""

        if len(detected_labels) == 1:
            return detected_labels[0]

        # Estrategia: retornar todos
        if self._multiple_detection_strategy == 'all':
            return detected_labels

        # Estrategia: mayor similitud
        elif self._multiple_detection_strategy == 'highest':
            best_template = max(detected_templates.keys(), key=lambda x: detected_templates[x])
            return mapping[best_template]

        # Estrategia: primero detectado
        elif self._multiple_detection_strategy == 'first':
            return detected_labels[0]

        # Estrategia: combinar (por defecto)
        else:
            # Buscar en reglas de combinación
            labels_tuple = tuple(sorted(detected_labels))
            for rule_labels, combined_label in self._combination_rules.items():
                if set(rule_labels) == set(detected_labels):
                    return combined_label

            # Si no hay regla específica, crear etiqueta combinada
            return '+'.join(sorted(detected_labels))

    # MÉTODOS AUXILIARES

    def get_similarities_detail(self,
                                raw_text: str,
                                custom_templates: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """
        Obtiene el detalle de similitudes calculadas sin clasificar.

        Args:
            raw_text (str): Texto crudo del documento
            custom_templates (Optional[Dict[str, str]]): Plantillas personalizadas

        Returns:
            Dict[str, float]: Diccionario con similitudes por plantilla
        """
        if not raw_text or not raw_text.strip():
            return {}

        templates = custom_templates if custom_templates else self._templates_cache

        if not templates:
            return {}

        # Procesar texto
        clean_text = self.clean_text(raw_text)
        amplified_text = self.amplify_keywords(clean_text)

        # Calcular similitudes
        similarities = {}
        for name, template in templates.items():
            template_text = self.amplify_keywords(self.clean_text(template))
            similarity = self.calculate_cosine_similarity(amplified_text, template_text)
            similarities[name] = similarity

        return similarities

    def get_classification_config(self) -> Dict[str, Any]:
        """Retorna la configuración actual de clasificación."""
        return {
            'template_mapping': self._classification_mapping,
            'combination_rules': self._combination_rules,
            'multiple_detection_strategy': self._multiple_detection_strategy,
            'similarity_threshold': self.similarity_threshold,
            'default_not_detected_label': self.default_not_detected_label
        }

    def clear_cache(self) -> None:
        """Limpia el cache de plantillas y configuración."""
        self._templates_cache.clear()
        self._classification_mapping.clear()
        self._combination_rules.clear()
