#!/usr/bin/env python3
"""
벡터 차원별 문서 확인 스크립트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from services.supabase_client import supabase_service
from collections import defaultdict

print("=== DB에서 문서 조회 중 ===")

# 모든 문서의 embedding 차원 확인
response = supabase_service.client.table("policy_documents") \
    .select("id, embedding, metadata, content") \
    .execute()

docs_768 = []
docs_3072 = []
docs_other = []

for doc in response.data:
    embedding = doc.get("embedding")
    if embedding:
        dim = len(embedding)
        meta = doc.get("metadata", {})
        doc_info = {
            "id": doc.get("id"),
            "content_preview": doc.get("content", "")[:60],
            "metadata": meta,
            "dimension": dim  # 차원 추가
        }
        
        if dim == 768:
            docs_768.append(doc_info)
        elif dim == 3072:
            docs_3072.append(doc_info)
        else:
            docs_other.append(doc_info)

print(f"\n=== 벡터 차원별 문서 수 ===")
print(f"768차원:  {len(docs_768):4d}개")
print(f"3072차원: {len(docs_3072):4d}개")
print(f"기타:     {len(docs_other):4d}개")
print(f"총:       {len(docs_768) + len(docs_3072) + len(docs_other):4d}개")

if docs_other:
    print(f"\n=== 기타 차원 상세 ===")
    from collections import Counter
    other_dims = Counter([d["dimension"] for d in docs_other])
    for dim, count in sorted(other_dims.items()):
        print(f"  {dim}차원: {count}개")
    
    # 샘플 하나 보기
    if docs_other:
        sample = docs_other[0]
        print(f"\n샘플 문서:")
        print(f"  차원: {sample['dimension']}")
        print(f"  ID: {sample['id']}")
        print(f"  메타: {sample['metadata']}")

if docs_3072:
    print(f"\n=== 3072차원 문서 (대학별) ===")
    by_univ = defaultdict(list)
    
    for doc in docs_3072:
        meta = doc.get("metadata", {})
        univ = meta.get("university") or meta.get("fileName", "미분류")
        if isinstance(univ, str) and "/" in univ:
            univ = univ.split("/")[0]
        by_univ[str(univ)].append(doc)
    
    for univ in sorted(by_univ.keys()):
        docs = by_univ[univ]
        print(f"\n[{univ}] {len(docs)}개")
        for doc in docs[:3]:
            print(f"  - {doc['content_preview']}...")
        if len(docs) > 3:
            print(f"  ... 외 {len(docs)-3}개")

    # 연세대 상세
    print(f"\n=== 연세대학교 상세 ===")
    yonsei_768 = [d for d in docs_768 if "연세" in str(d.get("metadata", {}))]
    yonsei_3072 = [d for d in docs_3072 if "연세" in str(d.get("metadata", {}))]
    
    print(f"768차원:  {len(yonsei_768)}개")
    print(f"3072차원: {len(yonsei_3072)}개")
    
    if yonsei_3072:
        print(f"\n연세대 3072차원 문서:")
        for doc in yonsei_3072:
            print(f"  ID: {doc['id']}")
            print(f"  내용: {doc['content_preview']}...")
            print(f"  메타: {doc['metadata']}")
            print()
