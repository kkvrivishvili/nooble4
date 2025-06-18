import re
from typing import List, Set
from collections import Counter
import spacy
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from common.handlers import BaseHandler
from common.config import CommonAppSettings
from ..models import ChunkModel


class ChunkEnricherHandler(BaseHandler):
    """Handler for enriching chunks with keywords and tags"""
    
    def __init__(self, app_settings: CommonAppSettings):
        super().__init__(app_settings)
        
        # Initialize NLP tools
        try:
            # Download required NLTK data
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            self.stop_words = set(stopwords.words('english'))
        except:
            self._logger.warning("NLTK data not available, using basic stop words")
            self.stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        
        # Try to load spaCy model for better NER
        try:
            self.nlp = spacy.load("en_core_web_sm")
            self.use_spacy = True
        except:
            self._logger.warning("spaCy model not available, using basic keyword extraction")
            self.use_spacy = False
    
    async def enrich_chunks(self, chunks: List[ChunkModel]) -> List[ChunkModel]:
        """Enrich chunks with keywords and tags"""
        for chunk in chunks:
            # Extract keywords
            keywords = await self._extract_keywords(chunk.text)
            chunk.keywords = list(keywords)[:10]  # Top 10 keywords
            
            # Generate tags based on content analysis
            tags = await self._generate_tags(chunk.text, chunk.metadata)
            chunk.tags = list(tags)
            
        return chunks
    
    async def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        keywords = set()
        
        if self.use_spacy:
            # Use spaCy for better extraction
            doc = self.nlp(text)
            
            # Extract named entities
            for ent in doc.ents:
                if ent.label_ in ['PERSON', 'ORG', 'PRODUCT', 'TECH']:
                    keywords.add(ent.text.lower())
            
            # Extract noun phrases
            for chunk in doc.noun_chunks:
                if len(chunk.text.split()) <= 3:  # Max 3 words
                    keywords.add(chunk.text.lower())
        
        # Basic keyword extraction
        # Clean and tokenize
        text_lower = text.lower()
        text_clean = re.sub(r'[^\w\s]', ' ', text_lower)
        tokens = word_tokenize(text_clean) if 'word_tokenize' in globals() else text_clean.split()
        
        # Filter tokens
        filtered_tokens = [
            token for token in tokens 
            if len(token) > 3 and token not in self.stop_words and not token.isdigit()
        ]
        
        # Get most common terms
        word_freq = Counter(filtered_tokens)
        common_words = [word for word, _ in word_freq.most_common(20)]
        keywords.update(common_words)
        
        # Extract technical terms (camelCase, snake_case, etc.)
        technical_terms = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b', text)  # CamelCase
        technical_terms += re.findall(r'\b\w+_\w+\b', text)  # snake_case
        technical_terms += re.findall(r'\b\w+-\w+\b', text)  # kebab-case
        
        keywords.update([term.lower() for term in technical_terms])
        
        return sorted(list(keywords))
    
    async def _generate_tags(self, text: str, metadata: Dict) -> Set[str]:
        """Generate tags based on content analysis"""
        tags = set()
        
        # Category tags based on metadata
        if 'category' in metadata:
            tags.add(metadata['category'])
        
        # Technology detection
        tech_keywords = {
            'database': ['sql', 'database', 'query', 'table', 'index', 'postgres', 'mysql', 'mongodb'],
            'programming': ['python', 'javascript', 'java', 'code', 'function', 'class', 'method'],
            'devops': ['docker', 'kubernetes', 'ci/cd', 'deployment', 'container', 'aws', 'cloud'],
            'security': ['security', 'encryption', 'authentication', 'ssl', 'https', 'firewall'],
            'api': ['api', 'rest', 'graphql', 'endpoint', 'request', 'response'],
            'frontend': ['react', 'vue', 'angular', 'css', 'html', 'ui', 'ux'],
            'backend': ['server', 'backend', 'microservice', 'service', 'architecture'],
            'data': ['data', 'analytics', 'etl', 'pipeline', 'processing', 'ml', 'ai']
        }
        
        text_lower = text.lower()
        for tag, keywords in tech_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                tags.add(tag)
        
        # Document type tags
        if 'document_type' in metadata:
            tags.add(metadata['document_type'])
        
        # Language/format detection
        if any(term in text_lower for term in ['```', 'import', 'def ', 'function']):
            tags.add('code')
        if any(term in text_lower for term in ['chapter', 'section', 'introduction', 'conclusion']):
            tags.add('documentation')
        if any(term in text_lower for term in ['step 1', 'how to', 'tutorial', 'guide']):
            tags.add('tutorial')
            
        return tags
