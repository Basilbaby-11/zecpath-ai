"""Optional semantic intent classification using Sentence Transformers."""
from __future__ import annotations
from typing import Dict, List
import numpy as np
INTENT_EXAMPLES = {
 "skills": ["I have practical knowledge of Python and SQL.", "I am comfortable using programming languages and frameworks.", "My technical stack includes machine learning tools.", "I have worked with databases, APIs, and software development tools."],
 "experience": ["I have two years of professional work experience.", "I completed a six month internship at a technology company.", "I am a fresher with no previous employment experience.", "I built projects during my academic studies."],
 "availability": ["I can start work immediately.", "I need to serve a thirty day notice period.", "I will be available to join next month.", "My earliest joining date is in two weeks."],
 "salary_expectation": ["I expect a monthly salary of twenty five thousand rupees.", "My expected annual compensation is five lakh rupees.", "I am looking for a salary package in this range.", "My expected cost to company is six LPA."]}
class SemanticIntentClassifier:
 """Cosine similarity against labeled examples; similarity is not probability."""
 def __init__(self, model_name="sentence-transformers/all-MiniLM-L6-v2", threshold=0.38, margin=0.025, model=None):
  if not 0 <= threshold <= 1: raise ValueError("threshold must be between 0 and 1")
  self.model_name,self.threshold,self.margin=model_name,threshold,margin
  self._model,self._prototypes=model,None
 def _load_model(self):
  if self._model is None:
   try: from sentence_transformers import SentenceTransformer
   except ImportError as exc: raise RuntimeError("Install requirements-day25-semantic.txt to enable semantic mode.") from exc
   self._model=SentenceTransformer(self.model_name)
  return self._model
 @staticmethod
 def _normalize(vectors):
  vectors=np.asarray(vectors,dtype=float)
  if vectors.ndim==1: vectors=vectors.reshape(1,-1)
  return vectors/np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-12)
 def _build_prototypes(self):
  if self._prototypes is None:
   model=self._load_model()
   self._prototypes={k:self._normalize(model.encode(v,convert_to_numpy=True)) for k,v in INTENT_EXAMPLES.items()}
 def score(self,text:str)->Dict[str,float]:
  if not isinstance(text,str): raise TypeError("text must be a string")
  if not text.strip(): return {}
  self._build_prototypes(); vector=self._normalize(self._load_model().encode([text],convert_to_numpy=True))[0]
  return {k:float(np.max(v@vector)) for k,v in self._prototypes.items()}
 def classify(self,text:str)->List[str]:
  scores=self.score(text)
  if not scores: return ["unknown"]
  ranked=sorted(scores.items(),key=lambda x:x[1],reverse=True)
  if ranked[0][1]<self.threshold: return ["unknown"]
  selected=[k for k,v in ranked if v>=self.threshold and ranked[0][1]-v<=self.margin]
  return selected or ["unknown"]
