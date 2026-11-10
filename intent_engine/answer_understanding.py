"""Entry point for plain-text answers and Day 24 STT transcript payloads."""
from typing import Any,Dict,Optional
from .answer_validator import AnswerValidator
from .entity_extractor import EntityExtractor
from .intent_classifier import IntentClassifier
from .off_topic_detector import OffTopicDetector
from .schemas import UnderstandingResult
from .day24_adapter import Day24TranscriptAdapter
class AnswerUnderstandingEngine:
 def __init__(self,semantic:bool=True,semantic_model_name:str="sentence-transformers/all-MiniLM-L6-v2",semantic_threshold:float=0.38):
  self.classifier=IntentClassifier(); self.extractor=EntityExtractor(); self.detector=OffTopicDetector(); self.validator=AnswerValidator()
  self.semantic_enabled=semantic; self.semantic_classifier=None
  if semantic:
   from .semantic_intent_classifier import SemanticIntentClassifier
   self.semantic_classifier=SemanticIntentClassifier(model_name=semantic_model_name,threshold=semantic_threshold)
 def understand(self,answer:str,question:str="",*,transcript_metadata:Optional[Dict[str,Any]]=None)->Dict[str,Any]:
  if not isinstance(answer,str) or not isinstance(question,str): raise TypeError("answer and question must be strings")
  metadata=transcript_metadata or {}; intents=self.classifier.classify(answer); semantic_scores={}
  if self.semantic_classifier and answer.strip():
   semantic_scores=self.semantic_classifier.score(answer); sem=self.semantic_classifier.classify(answer)
   if sem != ["unknown"]: intents=sorted(set(([] if intents==["unknown"] else intents)+sem))
  expected=self.classifier.expected_intents(question); entities=self.extractor.extract(answer)
  off_topic=self.detector.is_off_topic(question,intents); validation=self.validator.validate(answer,expected,entities,off_topic)
  speaker=metadata.get("speaker"); incomplete=any(bool(metadata.get(k,False)) for k in ("partial","interrupted","silence_detected")); non_candidate=speaker not in (None,"candidate")
  if incomplete or non_candidate:
   validation["is_complete"]=False
   if metadata.get("silence_detected") and not answer.strip(): validation["is_vague"]=True
   if non_candidate: validation["follow_up_question"]=None
  result=UnderstandingResult(intent=intents[0],intents=intents,entities=entities,is_off_topic=off_topic,confidence=None,metadata={"engine":"hybrid_semantic_v2" if self.semantic_enabled else "rule_based_baseline_v1","expected_intents":expected,"transcript_metadata":metadata,"semantic_scores":semantic_scores,"semantic_enabled":self.semantic_enabled,"turn_eligible_for_final_answer":not(incomplete or non_candidate)},**validation)
  return result.to_dict()
 def understand_stt_result(self,stt_result:Any,question:str="",*,question_id:Optional[str]=None,sequence_no:int=1,speaker:str="candidate",interrupted:bool=False,partial:bool=False)->Dict[str,Any]:
  payload=Day24TranscriptAdapter.from_stt_result(stt_result,question=question,question_id=question_id,sequence_no=sequence_no,speaker=speaker,interrupted=interrupted,partial=partial)
  return self.understand(**payload)
 def understand_turn(self,turn:Dict[str,Any],question:str="")->Dict[str,Any]:
  return self.understand(**Day24TranscriptAdapter.from_normalized_turn(turn,question=question))
