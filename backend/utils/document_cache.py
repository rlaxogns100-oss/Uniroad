"""
문서 조회 결과 캐싱 시스템

Supabase에서 조회한 문서 데이터를 메모리에 캐싱하여 
반복 조회 시 성능을 향상시킵니다.
"""

import time
import hashlib
import json
from typing import Any, Dict, Optional
from collections import OrderedDict
import threading


class DocumentCache:
    """문서 조회 결과 캐시 (LRU)"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Args:
            max_size: 최대 캐시 항목 수
            ttl_seconds: 캐시 유효 시간 (초, 기본 1시간)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, cache_type: str, **kwargs) -> str:
        """캐시 키 생성"""
        # 정렬된 키-값 쌍으로 일관된 키 생성
        sorted_params = sorted(kwargs.items())
        key_string = f"{cache_type}:{json.dumps(sorted_params, sort_keys=True)}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, cache_type: str, **kwargs) -> Optional[Any]:
        """
        캐시에서 데이터 조회
        
        Args:
            cache_type: 캐시 타입 (metadata, chunks, admission_results 등)
            **kwargs: 조회 조건 (예: university="서울대", filename="...")
            
        Returns:
            캐시된 데이터 또는 None
        """
        key = self._generate_key(cache_type, **kwargs)
        
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                
                # TTL 체크
                if time.time() - entry['timestamp'] > self.ttl_seconds:
                    # 만료된 캐시 삭제
                    del self._cache[key]
                    self._misses += 1
                    return None
                
                # LRU: 최근 사용으로 이동
                self._cache.move_to_end(key)
                self._hits += 1
                
                return entry['data']
            else:
                self._misses += 1
                return None
    
    def set(self, cache_type: str, data: Any, **kwargs):
        """
        캐시에 데이터 저장
        
        Args:
            cache_type: 캐시 타입
            data: 저장할 데이터
            **kwargs: 조회 조건
        """
        key = self._generate_key(cache_type, **kwargs)
        
        with self._lock:
            # 최대 크기 초과 시 가장 오래된 항목 삭제
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._cache.popitem(last=False)
            
            self._cache[key] = {
                'data': data,
                'timestamp': time.time()
            }
            self._cache.move_to_end(key)
    
    def invalidate(self, cache_type: Optional[str] = None, **kwargs):
        """
        캐시 무효화
        
        Args:
            cache_type: 특정 타입만 무효화 (None이면 전체)
            **kwargs: 특정 조건의 캐시만 무효화
        """
        with self._lock:
            if cache_type is None and not kwargs:
                # 전체 캐시 삭제
                self._cache.clear()
            elif cache_type and not kwargs:
                # 특정 타입의 모든 캐시 삭제
                keys_to_delete = [
                    key for key in self._cache.keys()
                    if key.startswith(hashlib.md5(cache_type.encode()).hexdigest()[:8])
                ]
                for key in keys_to_delete:
                    del self._cache[key]
            else:
                # 특정 키 삭제
                key = self._generate_key(cache_type, **kwargs)
                if key in self._cache:
                    del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': round(hit_rate, 2),
                'total_requests': total_requests
            }
    
    def clear_stats(self):
        """통계 초기화"""
        with self._lock:
            self._hits = 0
            self._misses = 0


# 전역 캐시 인스턴스
_document_cache = DocumentCache(max_size=100, ttl_seconds=3600)


def get_document_cache() -> DocumentCache:
    """전역 캐시 인스턴스 반환"""
    return _document_cache


# 편의 함수들
def cache_get(cache_type: str, **kwargs) -> Optional[Any]:
    """캐시에서 데이터 조회"""
    return _document_cache.get(cache_type, **kwargs)


def cache_set(cache_type: str, data: Any, **kwargs):
    """캐시에 데이터 저장"""
    _document_cache.set(cache_type, data, **kwargs)


def cache_invalidate(cache_type: Optional[str] = None, **kwargs):
    """캐시 무효화"""
    _document_cache.invalidate(cache_type, **kwargs)


def cache_stats() -> Dict[str, Any]:
    """캐시 통계"""
    return _document_cache.get_stats()
