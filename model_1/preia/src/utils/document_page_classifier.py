import re
import math
import unicodedata
import logging
from typing import List, Dict, Tuple, Optional, Set, Any, Union
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


class TfidfVectorizer:
    """Implementación de TF-IDF vectorizer."""

    def __init__(self, ngram_range=(1, 1)):
        self.ngram_range = ngram_range
        self.vocabulary_ = {}
        self.idf_ = {}
        self.feature_names_ = []

    def _generate_ngrams(self, tokens: List[str]) -> List[str]:
        ngrams = []
        min_n, max_n = self.ngram_range

        for n in range(min_n, max_n + 1):
            for i in range(len(tokens) - n + 1):
                ngram = ' '.join(tokens[i:i + n])
                ngrams.append(ngram)

        return ngrams

    def _tokenize(self, text: str) -> List[str]:
        return text.split()

    def fit_transform(self, documents: List[str]):
        # 1. Tokenizar y generar n-gramas
        doc_ngrams = []
        all_ngrams = set()

        for doc in documents:
            tokens = self._tokenize(doc)
            ngrams = self._generate_ngrams(tokens)
            doc_ngrams.append(ngrams)
            all_ngrams.update(ngrams)

        # 2. Crear vocabulario
        self.feature_names_ = sorted(list(all_ngrams))
        self.vocabulary_ = {term: idx for idx, term in enumerate(self.feature_names_)}

        # 3. Calcular IDF
        num_docs = len(documents)
        doc_freq = defaultdict(int)

        for ngrams in doc_ngrams:
            unique_ngrams = set(ngrams)
            for ngram in unique_ngrams:
                doc_freq[ngram] += 1

        self.idf_ = {}
        for term in self.feature_names_:
            self.idf_[term] = math.log(num_docs / doc_freq[term]) + 1

        # 4. Calcular TF-IDF
        tfidf_matrix = []

        for ngrams in doc_ngrams:
            tf_counter = Counter(ngrams)
            doc_length = len(ngrams)

            tfidf_vector = []
            for term in self.feature_names_:
                tf = tf_counter[term] / doc_length if doc_length > 0 else 0
                tfidf = tf * self.idf_[term]
                tfidf_vector.append(tfidf)

            # Normalizar L2
            norm = math.sqrt(sum(val ** 2 for val in tfidf_vector))
            if norm > 0:
                tfidf_vector = [val / norm for val in tfidf_vector]

            tfidf_matrix.append(tfidf_vector)

        return tfidf_matrix


def cosine_similarity(X: List[List[float]], Y: List[List[float]]) -> List[List[float]]:
    """Calcula similitud coseno entre matrices de vectores."""
    similarities = []

    for x_vec in X:
        row_similarities = []
        for y_vec in Y:
            dot_product = sum(a * b for a, b in zip(x_vec, y_vec))
            row_similarities.append(dot_product)
        similarities.append(row_similarities)

    return similarities


class DocumentPageClassifier:
    """
    Clasificador reutilizable de páginas de documentos usando ventanas deslizantes
    y similitud TF-IDF con plantillas configurables.
    """
    def set_regex_patterns(self, patterns: List[str]) -> None:
        """
        Establece los patrones de regex para la clasificación de páginas.
        """
        self.regex_patterns = patterns

    def __init__(self,
                 similarity_threshold: float = 0.10,
                 max_page_id: int = 15,
                 boost_factor: float = 0.08,
                 language: str = 'spanish',
                 enable_windowing: bool = True,
                 window_sizes: List[int] = [1, 2]):
        """
        Inicializa el clasificador.

        Args:
            similarity_threshold: Umbral mínimo de similitud para clasificación
            max_page_id: ID máximo de página a considerar
            boost_factor: Factor de boost para palabras clave específicas
            language: Idioma para stopwords ('spanish', 'english')
            enable_windowing: Si usar ventanas deslizantes o solo páginas individuales
            window_sizes: Tamaños de ventanas a generar [1, 2] = páginas individuales + pares
        """
        self.similarity_threshold = similarity_threshold
        self.max_page_id = max_page_id
        self.boost_factor = boost_factor
        self.enable_windowing = enable_windowing
        self.window_sizes = window_sizes

        # Configuración de procesamiento
        self.stopwords = self._get_stopwords(language)
        self.weighted_keywords = {}

        # Templates y configuración de clasificación
        self.templates = {}
        self.template_labels = {}
        self.synonym_keywords = {}  # Para boost específico por categoría
        self.combination_rules = {}

        # TF-IDF
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2))
        # Patrones regex opcionales por etiqueta (e.g., {'CF': [patrones...]})
        self._regex_patterns = {}

    def _get_stopwords(self, language: str) -> Set[str]:
        """Obtiene stopwords según idioma."""
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
                'will', 'with', 'this', 'but', 'they', 'have', 'had', 'what', 'said',
                'each', 'which', 'she', 'do', 'how', 'their', 'if', 'up', 'out', 'many', 'then',
                'them', 'these', 'so', 'some', 'her', 'would', 'make', 'like', 'into', 'him',
                'time', 'two', 'more', 'go', 'no', 'way', 'could', 'my', 'than', 'first',
                'been', 'call', 'who', 'oil', 'now', 'find', 'long', 'down', 'day',
                'did', 'get', 'come', 'made', 'may', 'part'
            }
        }
        return stopwords_dict.get(language, stopwords_dict['spanish'])

    # CONFIGURACIÓN METHODS

    def configure_classification(self,
                                 template_mapping: Dict[str, str],
                                 combination_rules: Optional[Dict[Tuple[str, ...], str]] = None) -> None:
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
        if not template_mapping:
            raise ValueError("template_mapping no puede estar vacío")


        # Usar las propiedades existentes
        self.template_labels = template_mapping.copy()
        self.combination_rules = combination_rules or {}

        logger.info(f"Configuración de clasificación establecida: {len(template_mapping)} mapeos")

    def add_template(self, name: str, template: str, classification_label: str) -> None:
        """
        Agrega una plantilla individual con su etiqueta de clasificación.

        Args:
            name (str): Nombre identificador de la plantilla
            template (str): Contenido de la plantilla
            classification_label (str): Etiqueta de clasificación para esta plantilla
        """
        if not name or not name.strip():
            raise ValueError("El nombre de la plantilla no puede estar vacío")

        if not template or not template.strip():
            raise ValueError("El contenido de la plantilla no puede estar vacío")

        if not classification_label or not classification_label.strip():
            raise ValueError("La etiqueta de clasificación no puede estar vacía")

        # Usar las propiedades existentes
        self.templates[name] = template
        self.template_labels[name] = classification_label

        logger.info(f"Plantilla '{name}' agregada con etiqueta '{classification_label}'")

    def set_templates(self, templates: Dict[str, str]) -> None:
        """
        Establece múltiples plantillas. Requiere configuración previa de mapeo.

        Args:
            templates (Dict[str, str]): Diccionario con plantillas por nombre
        """
        if not templates:
            raise ValueError("El diccionario de templates no puede estar vacío")

        # Validar que todas las plantillas tengan mapeo configurado
        unmapped_templates = set(templates.keys()) - set(self.template_labels.keys())
        if unmapped_templates:
            raise ValueError(f"Templates sin mapeo de clasificación configurado: {unmapped_templates}. "
                             f"Use configure_classification() primero o add_template() para cada uno.")

        # Validar contenido de templates
        invalid_templates = [name for name, content in templates.items()
                             if not content or not content.strip()]
        if invalid_templates:
            raise ValueError(f"Templates con contenido vacío: {invalid_templates}")

        # Usar la propiedad existente
        self.templates = templates.copy()

        logger.info(f"Establecidas {len(templates)} plantillas")

    def configure_keyword_boosting(self,
                                   weighted_keywords: Optional[Dict[str, Union[int, float]]] = None,
                                   category_synonyms: Optional[Dict[str, List[str]]] = None) -> None:
        """
        Configura el sistema de boost por palabras clave.

        Args:
            weighted_keywords (Optional[Dict[str, Union[int, float]]]): Palabras clave con pesos
                Ejemplo: {'balance': 2.0, 'activo': 1.5, 'pasivo': 1.5}
            category_synonyms (Optional[Dict[str, List[str]]]): Sinónimos por categoría
                Ejemplo: {'BS': ['balance', 'estado financiero'], 'PL': ['resultados', 'ingresos']}
        """
        if weighted_keywords is not None:
            self.set_weighted_keywords(weighted_keywords)

        if category_synonyms is not None:
            self.set_synonym_keywords(category_synonyms)

        logger.info("Configuración de boost por keywords establecida")

    def set_weighted_keywords(self, keywords: Dict[str, Union[int]]) -> None:
        """
        Establece palabras clave con ponderación.

        Args:
            keywords: Diccionario {palabra_clave: peso}
        """
        if not keywords:
            logger.warning("Diccionario de keywords vacío, limpiando configuración previa")
            self.weighted_keywords = {}
            return

        # Validar pesos
        invalid_weights = {k: v for k, v in keywords.items()
                           if not isinstance(v, (int, float)) or v < 0}
        if invalid_weights:
            raise ValueError(f"Pesos inválidos (deben ser números >= 0): {invalid_weights}")

        # Limpiar keywords y normalizar pesos
        cleaned_keywords = {}
        for keyword, weight in keywords.items():
            clean_keyword = self._clean_text(keyword)
            if clean_keyword:  # Solo agregar si queda algo después de limpiar
                cleaned_keywords[clean_keyword] = int(weight)

        self.weighted_keywords = cleaned_keywords
        logger.info(f"Configuradas {len(cleaned_keywords)} palabras clave ponderadas")

    def set_synonym_keywords(self, category_synonyms: Dict[str, List[str]]) -> None:
        """
        Configura sinónimos específicos por categoría para boost adicional.

        Args:
            category_synonyms: {etiqueta_categoria: [lista_de_sinonimos]}
        """
        if not category_synonyms:
            logger.warning("Diccionario de sinónimos vacío, limpiando configuración previa")
            self.synonym_keywords = {}
            return

        self.synonym_keywords = {}
        total_synonyms = 0

        for category, synonyms in category_synonyms.items():
            if not synonyms:
                logger.warning(f"Lista de sinónimos vacía para categoría '{category}'")
                continue

            # Limpiar sinónimos y filtrar vacíos
            clean_synonyms = []
            for syn in synonyms:
                clean_syn = self._clean_text(syn)
                if clean_syn:  # Solo agregar si queda algo después de limpiar
                    clean_synonyms.append(clean_syn)

            if clean_synonyms:
                self.synonym_keywords[category] = clean_synonyms
                total_synonyms += len(clean_synonyms)
            else:
                logger.warning(f"No hay sinónimos válidos para categoría '{category}' después de la limpieza")

        logger.info(
            f"Configurados sinónimos para {len(self.synonym_keywords)} categorías ({total_synonyms} sinónimos totales)")

    def set_regex_patterns(self, per_label_patterns: Dict[str, List[str]]) -> None:
        """
        Configura patrones regex por etiqueta para detección adicional por página.

        Args:
            per_label_patterns: Diccionario {'LABEL': [patron_regex, ...]}
        """
        if per_label_patterns is None:
            self._regex_patterns = {}
            return

        # Validar estructura básica
        cleaned: Dict[str, List[str]] = {}
        for label, patterns in per_label_patterns.items():
            if not isinstance(label, str) or not label.strip():
                continue
            if not isinstance(patterns, list) or not patterns:
                continue
            # Filtrar patrones vacíos
            valid_patterns = [p for p in patterns if isinstance(p, str) and p.strip()]
            if valid_patterns:
                cleaned[label] = valid_patterns

        self._regex_patterns = cleaned
        logger.info(f"Configurados patrones regex para {len(self._regex_patterns)} etiquetas")

    def update_classification_params(self,
                                     similarity_threshold: Optional[float] = None,
                                     max_page_id: Optional[int] = None,
                                     boost_factor: Optional[float] = None,
                                     enable_windowing: Optional[bool] = None,
                                     window_sizes: Optional[List[int]] = None) -> None:
        """
        Actualiza parámetros de clasificación en tiempo de ejecución.

        Args:
            similarity_threshold: Nuevo umbral de similitud (0-1)
            max_page_id: Nuevo ID máximo de página (>= 1)
            boost_factor: Nuevo factor de boost (>= 0)
            enable_windowing: Si habilitar ventanas deslizantes
            window_sizes: Nuevos tamaños de ventana
        """
        if similarity_threshold is not None:
            if not 0 <= similarity_threshold <= 1:
                raise ValueError("similarity_threshold debe estar entre 0 y 1")
            self.similarity_threshold = similarity_threshold

        if max_page_id is not None:
            if max_page_id < 1:
                raise ValueError("max_page_id debe ser >= 1")
            self.max_page_id = max_page_id

        if boost_factor is not None:
            if boost_factor < 0:
                raise ValueError("boost_factor debe ser >= 0")
            self.boost_factor = boost_factor

        if enable_windowing is not None:
            self.enable_windowing = enable_windowing

        if window_sizes is not None:
            if not window_sizes or any(size < 1 for size in window_sizes):
                raise ValueError("window_sizes debe contener enteros >= 1")
            self.window_sizes = window_sizes

        logger.info("Parámetros de clasificación actualizados")

    def get_configuration_status(self) -> Dict[str, Any]:
        """
        Retorna el estado actual de la configuración.

        Returns:
            Diccionario con información detallada de configuración
        """
        return {
            # Parámetros principales
            'similarity_threshold': self.similarity_threshold,
            'max_page_id': self.max_page_id,
            'boost_factor': self.boost_factor,
            'enable_windowing': self.enable_windowing,
            'window_sizes': self.window_sizes,

            # Estado de configuración
            'templates_configured': len(self.templates),
            'labels_configured': len(self.template_labels),
            'weighted_keywords': len(self.weighted_keywords),
            'synonym_categories': len(self.synonym_keywords),
            'combination_rules': len(self.combination_rules),

            # Detalles
            'template_names': list(self.templates.keys()),
            'available_labels': list(set(self.template_labels.values())),
            'configured_categories': list(self.synonym_keywords.keys()),

            # Validación
            'is_ready_for_classification': bool(
                self.templates and
                self.template_labels and
                set(self.templates.keys()).issubset(set(self.template_labels.keys()))
            ),

            # Estrategia configurada (si existe)
            'multiple_detection_strategy': getattr(self, '_multiple_detection_strategy', 'combine')
        }

    def reset_configuration(self, components: Optional[List[str]] = None) -> None:
        """
        Reinicia componentes específicos de la configuración.

        Args:
            components: Lista de componentes a reiniciar. Si None, reinicia todo.
                       Opciones: ['templates', 'keywords', 'synonyms', 'rules', 'params']
        """
        if components is None:
            components = ['templates', 'keywords', 'synonyms', 'rules']

        if 'templates' in components:
            self.templates = {}
            self.template_labels = {}
            logger.info("Templates y labels reiniciados")

        if 'keywords' in components:
            self.weighted_keywords = {}
            logger.info("Keywords ponderadas reiniciadas")

        if 'synonyms' in components:
            self.synonym_keywords = {}
            logger.info("Sinónimos reiniciados")

        if 'rules' in components:
            self.combination_rules = {}
            logger.info("Reglas de combinación reiniciadas")

        if 'params' in components:
            # Restaurar valores por defecto
            self.similarity_threshold = 0.10
            self.max_page_id = 15
            self.boost_factor = 0.08
            self.enable_windowing = True
            self.window_sizes = [1, 2]
            logger.info("Parámetros restaurados a valores por defecto")

        logger.info(f"Configuración reiniciada: {components}")

    # Los métodos set_combination_rules se mantiene igual ya que está bien diseñado
    def set_combination_rules(self, rules: Dict[Tuple[str, ...], str]) -> None:
        """Configura reglas para combinar múltiples detecciones."""
        if not rules:
            logger.warning("Diccionario de reglas vacío, limpiando configuración previa")
            self.combination_rules = {}
            return

        # Validar estructura de las reglas
        invalid_rules = []
        for key, value in rules.items():
            if not isinstance(key, tuple) or len(key) < 2:
                invalid_rules.append(key)
            elif not isinstance(value, str) or not value.strip():
                invalid_rules.append(key)

        if invalid_rules:
            raise ValueError(f"Reglas inválidas (deben ser tuplas de 2+ elementos -> str no vacío): {invalid_rules}")

        self.combination_rules = rules
        logger.info(f"Configuradas {len(rules)} reglas de combinación")

    # MÉTODOS DE PROCESAMIENTO

    def _clean_text(self, text: str) -> str:
        """Limpia y normaliza el texto."""
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
        text = re.sub(r"[^a-z\sáéíóúñ]", " ", text.lower())
        text = re.sub(r"\s+", " ", text).strip()
        return " ".join([w for w in text.split() if w and w not in self.stopwords])

    def _amplify_keywords(self, text: str) -> str:
        """Amplifica palabras clave según su ponderación."""
        words = text.split()
        extra = []
        for word, weight in self.weighted_keywords.items():
            count = words.count(word)
            if count > 0:
                extra.extend([word] * (weight - 1) * count)
        return " ".join(words + extra)

    def _split_pages(self, text: str) -> List[Tuple[str, str]]:
        """Extrae páginas del texto usando separadores ###PAGE_ID:XXX###"""
        pattern = re.compile(r"###PAGE_ID:(\d+)###")
        matches = list(pattern.finditer(text))

        if not matches:
            return [("1", text)]

        pages = []
        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            page_id = match.group(1).lstrip("0") or "0"

            # Filtrar páginas según max_page_id
            if int(page_id) <= self.max_page_id:
                pages.append((page_id, text[start:end]))

        return pages

    def _create_windows(self, pages: List[Tuple[str, str]]) -> List[Dict]:
        """Crea ventanas de análisis según configuración."""
        windows = []

        # Siempre incluir páginas individuales si 1 está en window_sizes
        if 1 in self.window_sizes:
            for page_id, raw_text in pages:
                windows.append({
                    "page_ids": [page_id],
                    "combined_text": raw_text,
                    "window_type": "single",
                    "display_id": f"Página {page_id}"
                })

        # Ventanas de tamaño > 1 si está habilitado
        if self.enable_windowing:
            for window_size in self.window_sizes:
                if window_size > 1 and window_size <= len(pages):
                    for i in range(len(pages) - window_size + 1):
                        window_pages = pages[i:i + window_size]

                        page_ids = [p[0] for p in window_pages]
                        combined_text = " ".join([p[1] for p in window_pages])

                        if window_size == 2:
                            display_id = f"Páginas {page_ids[0]}-{page_ids[1]}"
                        else:
                            display_id = f"Páginas {page_ids[0]}-{page_ids[-1]} ({window_size})"

                        windows.append({
                            "page_ids": page_ids,
                            "combined_text": combined_text,
                            "window_type": f"window_{window_size}",
                            "display_id": display_id
                        })

        return windows

    def _contains_synonyms(self, clean_text: str, synonyms: List[str]) -> bool:
        """Verifica si el texto contiene alguno de los sinónimos."""
        return any(syn in clean_text for syn in synonyms)

    def _apply_synonym_boost(self, similarities: Dict[str, float], clean_text: str) -> Dict[str, float]:
        """Aplica boost basado en sinónimos específicos por categoría."""
        boosted_similarities = similarities.copy()

        for category, synonyms in self.synonym_keywords.items():
            if self._contains_synonyms(clean_text, synonyms):
                # Buscar templates que corresponden a esta categoría
                for template_name, template_label in self.template_labels.items():
                    if template_label == category:
                        boosted_similarities[template_name] = min(
                            similarities[template_name] + self.boost_factor, 1.0
                        )
            else:
                # Si no contiene sinónimos, reducir similitud a 0
                for template_name, template_label in self.template_labels.items():
                    if template_label == category:
                        boosted_similarities[template_name] = 0.0

        return boosted_similarities

    # MÉTODO PRINCIPAL

    def classify_pages(self,
                       full_text: str,
                       templates: Optional[Dict[str, str]] = None,
                       template_labels: Optional[Dict[str, str]] = None,
                       top_n: int = 10) -> List[int]:
        """
        Clasifica páginas del documento y retorna lista de IDs de páginas relevantes.

        Args:
            full_text: Texto completo con separadores ###PAGE_ID:XXX###
            templates: Templates a usar (opcional, usa los configurados si no se pasa)
            template_labels: Etiquetas para templates (opcional)
            top_n: Número de mejores resultados a considerar

        Returns:
            Lista de IDs de páginas ordenados por relevancia
        """
        # Usar templates configurados o los pasados como parámetro
        if templates:
            if not template_labels:
                raise ValueError("template_labels es requerido cuando se pasan templates")
            working_templates = templates
            working_labels = template_labels
        else:
            working_templates = self.templates
            working_labels = self.template_labels

        if not working_templates:
            raise ValueError("No hay templates configurados")

        # 1. Extraer páginas
        pages_raw = self._split_pages(full_text)

        # Log estadísticas
        total_pages = len(re.findall(r"###PAGE_ID:(\d+)###", full_text))
        logger.info(f"Total páginas encontradas: {total_pages}, "
                    f"consideradas (≤{self.max_page_id}): {len(pages_raw)}")

        if not pages_raw:
            logger.warning("No hay páginas válidas para analizar")
            return []

        # 2. Crear ventanas
        windows = self._create_windows(pages_raw)
        logger.info(f"Total ventanas generadas: {len(windows)}")

        # 3. Procesar ventanas
        windows_processed = []
        for window in windows:
            clean_text = self._clean_text(window["combined_text"])
            amplified_text = self._amplify_keywords(clean_text)
            windows_processed.append(amplified_text)

        # 4. Procesar templates
        templates_processed = {}
        for name, template in working_templates.items():
            clean_template = self._clean_text(template)
            amplified_template = self._amplify_keywords(clean_template)
            templates_processed[name] = amplified_template

        # 5. Vectorizar: ventanas + templates
        all_docs = windows_processed + list(templates_processed.values())
        tfidf_matrix = self.vectorizer.fit_transform(all_docs)

        # 6. Separar matrices
        n_windows = len(windows_processed)
        X_windows = tfidf_matrix[:n_windows]
        X_templates = tfidf_matrix[n_windows:]

        # 7. Calcular similitudes
        similarities_matrix = cosine_similarity(X_windows, X_templates)

        # 8. Procesar resultados
        template_names = list(templates_processed.keys())
        results = []

        for i, window in enumerate(windows):
            # Similitudes base
            sim_dict = {
                template_names[j]: float(similarities_matrix[i][j])
                for j in range(len(template_names))
            }

            # Aplicar boost por sinónimos si está configurado
            if self.synonym_keywords:
                clean_window_text = self._clean_text(window["combined_text"])
                sim_dict = self._apply_synonym_boost(sim_dict, clean_window_text)

            # Determinar mejor clasificación
            best_template, best_similarity = max(sim_dict.items(), key=lambda x: x[1])
            classification = (working_labels[best_template]
                              if best_similarity >= self.similarity_threshold
                              else "NO_DETERMINADO")

            result = {
                "page_ids": window["page_ids"],
                "display_id": window["display_id"],
                "window_type": window["window_type"],
                "classification": classification,
                "best_similarity": round(best_similarity, 4),
                "similarities": {k: round(v, 4) for k, v in sim_dict.items()},
                "template_labels": {k: working_labels.get(k, 'UNKNOWN') for k in sim_dict.keys()}
            }

            results.append(result)

        # 9. Ordenar y obtener top resultados
        top_results = sorted(results, key=lambda x: x["best_similarity"], reverse=True)[:top_n]

        # 10. Log de resultados
        logger.info(f"TOP {min(top_n, len(top_results))} MEJORES SIMILITUDES:")
        for i, item in enumerate(top_results, 1):
            logger.info(f"{i}. {item['display_id']} ({item['window_type']}) - {item['classification']}")
            logger.info(f"   Similitud: {item['best_similarity']:.4f}")

        # 11. Extraer páginas únicas
        unique_pages = set()
        for result in top_results:
            for page_id in result["page_ids"]:
                unique_pages.add(int(page_id))

        final_pages = sorted(list(unique_pages))
        logger.info(f"PÁGINAS FINALES: {final_pages}")

        return final_pages

    def classify_pages_by_label(self,
                                full_text: str,
                                templates: Optional[Dict[str, str]] = None,
                                template_labels: Optional[Dict[str, str]] = None,
                                top_n: int = 10) -> Dict[str, List[int]]:
        """
        Clasifica páginas y retorna un diccionario de páginas por etiqueta.

        Combina similitud TF-IDF (para labels presentes en templates) con
        detección por regex (para labels configuradas en set_regex_patterns).

        Returns:
            Dict[str, List[int]]: {'BS': [...], 'PL': [...], 'CF': [...]} (según aplique)
        """
        # Preparar templates/labels de trabajo
        if templates:
            if not template_labels:
                raise ValueError("template_labels es requerido cuando se pasan templates")
            working_templates = templates
            working_labels = template_labels
        else:
            working_templates = self.templates
            working_labels = self.template_labels

        # Extraer páginas crudas
        pages_raw = self._split_pages(full_text)
        if not pages_raw:
            return {}

        # Si no hay templates configurados, aún podemos aplicar solo regex
        per_label_pages: Dict[str, Set[int]] = {}

        # Pipeline TF-IDF solo si hay templates
        if working_templates:
            windows = self._create_windows(pages_raw)

            windows_processed = []
            for window in windows:
                clean_text = self._clean_text(window["combined_text"])
                amplified_text = self._amplify_keywords(clean_text)
                windows_processed.append(amplified_text)

            templates_processed = {}
            for name, template in working_templates.items():
                clean_template = self._clean_text(template)
                amplified_template = self._amplify_keywords(clean_template)
                templates_processed[name] = amplified_template

            all_docs = windows_processed + list(templates_processed.values())
            tfidf_matrix = self.vectorizer.fit_transform(all_docs)

            n_windows = len(windows_processed)
            X_windows = tfidf_matrix[:n_windows]
            X_templates = tfidf_matrix[n_windows:]

            similarities_matrix = cosine_similarity(X_windows, X_templates)
            template_names = list(templates_processed.keys())

            # Asignar páginas a etiquetas según mejor similitud y umbral
            for i, window in enumerate(windows):
                sim_dict = {
                    template_names[j]: float(similarities_matrix[i][j])
                    for j in range(len(template_names))
                }

                if self.synonym_keywords:
                    clean_window_text = self._clean_text(window["combined_text"])
                    sim_dict = self._apply_synonym_boost(sim_dict, clean_window_text)

                best_template, best_similarity = max(sim_dict.items(), key=lambda x: x[1])
                if best_similarity >= self.similarity_threshold:
                    label = working_labels.get(best_template)
                    if label:
                        if label not in per_label_pages:
                            per_label_pages[label] = set()
                        for pid in window["page_ids"]:
                            per_label_pages[label].add(int(pid))

        #  TODO APLICAR REGEX POR PÁGINA SI HAY PATRONES CONFIGURADOS
        if self._regex_patterns:
            for page_id_str, page_text in pages_raw:
                try:
                    page_id = int(page_id_str)
                except Exception:
                    continue

                text_norm = page_text.lower()
                for label, patterns in self._regex_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, text_norm, re.IGNORECASE):
                            if label not in per_label_pages:
                                per_label_pages[label] = set()
                            per_label_pages[label].add(page_id)
                            break  # Evitar repetir misma página por múltiples patrones del mismo label

        # Convertir sets a listas ordenadas
        return {label: sorted(list(pages)) for label, pages in per_label_pages.items() if pages}

    def get_detailed_results(self,
                             full_text: str,
                             templates: Optional[Dict[str, str]] = None,
                             template_labels: Optional[Dict[str, str]] = None,
                             top_n: int = 10) -> List[Dict]:
        """
        Versión que retorna resultados detallados en lugar de solo IDs de páginas.

        Returns:
            Lista de diccionarios con información detallada de cada ventana
        """
        # Reutilizar la lógica de classify_pages pero retornar los resultados completos
        # (El código es idéntico hasta el paso 8, luego retorna results en lugar de páginas)

        working_templates = templates or self.templates
        working_labels = template_labels or self.template_labels

        if not working_templates:
            raise ValueError("No hay templates configurados")

        pages_raw = self._split_pages(full_text)
        if not pages_raw:
            return []

        windows = self._create_windows(pages_raw)

        windows_processed = []
        for window in windows:
            clean_text = self._clean_text(window["combined_text"])
            amplified_text = self._amplify_keywords(clean_text)
            windows_processed.append(amplified_text)

        templates_processed = {}
        for name, template in working_templates.items():
            clean_template = self._clean_text(template)
            amplified_template = self._amplify_keywords(clean_template)
            templates_processed[name] = amplified_template

        all_docs = windows_processed + list(templates_processed.values())
        tfidf_matrix = self.vectorizer.fit_transform(all_docs)

        n_windows = len(windows_processed)
        X_windows = tfidf_matrix[:n_windows]
        X_templates = tfidf_matrix[n_windows:]

        similarities_matrix = cosine_similarity(X_windows, X_templates)
        template_names = list(templates_processed.keys())
        results = []

        for i, window in enumerate(windows):
            sim_dict = {
                template_names[j]: float(similarities_matrix[i][j])
                for j in range(len(template_names))
            }

            if self.synonym_keywords:
                clean_window_text = self._clean_text(window["combined_text"])
                sim_dict = self._apply_synonym_boost(sim_dict, clean_window_text)

            best_template, best_similarity = max(sim_dict.items(), key=lambda x: x[1])
            classification = (working_labels[best_template]
                              if best_similarity >= self.similarity_threshold
                              else "NO_DETERMINADO")

            result = {
                "page_ids": window["page_ids"],
                "display_id": window["display_id"],
                "window_type": window["window_type"],
                "classification": classification,
                "best_similarity": round(best_similarity, 4),
                "similarities": {k: round(v, 4) for k, v in sim_dict.items()},
                "template_labels": {k: working_labels.get(k, 'UNKNOWN') for k in sim_dict.keys()}
            }
            results.append(result)

        # Retornar top resultados
        return sorted(results, key=lambda x: x["best_similarity"], reverse=True)[:top_n]


