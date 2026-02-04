"""
Google Analytics 4 데이터 조회 API - OAuth 2.0 인증
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Dimension,
    Metric,
    DateRange,
    OrderBy,
)
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# OAuth 2.0 스코프
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

# 토큰 저장 경로
TOKEN_PATH = Path(__file__).parent.parent / "credentials" / "token.json"
CREDENTIALS_PATH = Path(__file__).parent.parent / "client_secrets.json" / "client_secret_521257259578-h7a4pah36paar41ch87epc4883iftdmm.apps.googleusercontent.com.json"

class GA4Client:
    """GA4 데이터 조회 클라이언트 - OAuth 2.0 인증"""
    
    def __init__(self):
        self.property_id = os.getenv("GA4_PROPERTY_ID", "521910579")
        self.credentials = self._get_credentials()
        self.client = BetaAnalyticsDataClient(credentials=self.credentials)
    
    def _get_credentials(self):
        """OAuth 2.0 인증 처리"""
        credentials = None
        
        # 1. 저장된 토큰이 있으면 사용
        if TOKEN_PATH.exists():
            print(f"✅ 저장된 토큰 사용: {TOKEN_PATH}")
            credentials = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        
        # 2. 토큰이 없거나 만료되었으면 새로 인증
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                print("🔄 토큰 갱신 중...")
                credentials.refresh(Request())
            else:
                print("🔐 브라우저 인증 시작...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_PATH, SCOPES
                )
                credentials = flow.run_local_server(port=0)
            
            # 토큰 저장
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_PATH, "w") as token_file:
                token_file.write(credentials.to_json())
            print(f"✅ 토큰 저장 완료: {TOKEN_PATH}")
        
        return credentials
    
    def run_report(self, dimensions, metrics, date_ranges, order_bys=None):
        """GA4 리포트 실행"""
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name=d) for d in dimensions],
                metrics=[Metric(name=m) for m in metrics],
                date_ranges=[DateRange(start_date=dr["start"], end_date=dr["end"]) for dr in date_ranges],
                order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name=ob)) for ob in (order_bys or [])],
            )
            response = self.client.run_report(request)
            return response
        except Exception as e:
            print(f"GA4 리포트 오류: {e}")
            return None
    
    def get_event_data(self, days: int = 7):
        """이벤트별 발생 횟수 조회"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        response = self.run_report(
            dimensions=["eventName"],
            metrics=["eventCount"],
            date_ranges=[{
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }]
        )
        
        if not response:
            return []
        
        events = []
        for row in response.rows:
            event_name = row.dimension_values[0].value
            event_count = int(row.metric_values[0].value)
            events.append({
                "name": event_name,
                "count": event_count
            })
        
        # 발생 횟수 기준 정렬
        events.sort(key=lambda x: x["count"], reverse=True)
        
        # 비율 계산
        total = sum(e["count"] for e in events)
        for event in events:
            event["percentage"] = round((event["count"] / total) * 100) if total > 0 else 0
        
        return events
    
    def get_page_view_data(self, days: int = 7):
        """페이지별 방문 수 조회"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        response = self.run_report(
            dimensions=["pagePath"],
            metrics=["screenPageViews"],
            date_ranges=[{
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }]
        )
        
        if not response:
            return []
        
        pages = []
        for row in response.rows:
            page_path = row.dimension_values[0].value
            views = int(row.metric_values[0].value)
            pages.append({
                "page": page_path,
                "views": views
            })
        
        # 방문 수 기준 정렬
        pages.sort(key=lambda x: x["views"], reverse=True)
        
        return pages
    
    def get_timeseries_data(self, days: int = 7):
        """일별 이벤트 발생 추이 조회"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        response = self.run_report(
            dimensions=["date"],
            metrics=["eventCount"],
            date_ranges=[{
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }]
        )
        
        if not response:
            return []
        
        timeseries = []
        for row in response.rows:
            date_str = row.dimension_values[0].value
            # YYYYMMDD 형식을 YYYY-MM-DD로 변환
            date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            events = int(row.metric_values[0].value)
            timeseries.append({
                "date": date_formatted,
                "events": events
            })
        
        return timeseries
    
    def get_path_analysis(self, days: int = 7):
        """경로 분석 데이터 조회 - 페이지 시퀀스"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # 페이지 경로와 다음 페이지 조회
        response = self.run_report(
            dimensions=["pagePath", "nextPagePath"],
            metrics=["screenPageViews"],
            date_ranges=[{
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }]
        )
        
        if not response:
            return {"nodes": [], "links": []}
        
        nodes_set = set()
        links = []
        
        for row in response.rows:
            source = row.dimension_values[0].value
            target = row.dimension_values[1].value
            value = int(row.metric_values[0].value)
            
            if source and target and source != target:
                nodes_set.add(source)
                nodes_set.add(target)
                links.append({
                    "source": source,
                    "target": target,
                    "value": value
                })
        
        # 링크 기준 정렬 (상위 10개)
        links.sort(key=lambda x: x["value"], reverse=True)
        links = links[:10]
        
        # 노드 생성
        nodes = [{"name": node} for node in nodes_set]
        
        return {
            "nodes": nodes,
            "links": links
        }
    
    def get_entry_exit_pages(self, days: int = 7):
        """진입점과 이탈점 분석"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # 진입점 조회
        entry_response = self.run_report(
            dimensions=["landingPage"],
            metrics=["sessions"],
            date_ranges=[{
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }]
        )
        
        # 이탈점 조회
        exit_response = self.run_report(
            dimensions=["exitPage"],
            metrics=["sessions"],
            date_ranges=[{
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }]
        )
        
        entry_pages = []
        if entry_response:
            for row in entry_response.rows:
                page = row.dimension_values[0].value
                sessions = int(row.metric_values[0].value)
                if page:
                    entry_pages.append({"page": page, "sessions": sessions})
        
        exit_pages = []
        if exit_response:
            for row in exit_response.rows:
                page = row.dimension_values[0].value
                sessions = int(row.metric_values[0].value)
                if page:
                    exit_pages.append({"page": page, "sessions": sessions})
        
        # 상위 5개만
        entry_pages.sort(key=lambda x: x["sessions"], reverse=True)
        exit_pages.sort(key=lambda x: x["sessions"], reverse=True)
        
        return {
            "entry_pages": entry_pages[:5],
            "exit_pages": exit_pages[:5]
        }
    
    def get_funnel_analysis(self, days: int = 7):
        """깔때기 분석 - 3단계 전환 추적"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # 단계별 조회 설정
        stages_config = [
            {
                "name": "랜딩페이지_방문",
                "dimensions": ["pagePath"],
                "metrics": ["screenPageViews"],
                "filter_path": "/"  # 홈페이지
            },
            {
                "name": "챗봇_페이지_방문",
                "dimensions": ["pagePath"],
                "metrics": ["screenPageViews"],
                "filter_path": "/chat"  # 챗봇 페이지
            },
            {
                "name": "실제_질문_전송",
                "dimensions": ["eventName"],
                "metrics": ["eventCount"],
                "filter_event": "질문_전송_태그"  # 질문 전송 이벤트
            }
        ]
        
        stage_data = []
        
        for i, stage_config in enumerate(stages_config):
            try:
                response = self.run_report(
                    dimensions=stage_config["dimensions"],
                    metrics=stage_config["metrics"],
                    date_ranges=[{
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    }]
                )
                
                if response and len(response.rows) > 0:
                    total_count = 0
                    
                    if "filter_path" in stage_config:
                        # 페이지 경로 필터링
                        for row in response.rows:
                            page_path = row.dimension_values[0].value
                            if stage_config["filter_path"] in page_path:
                                total_count += int(row.metric_values[0].value)
                    elif "filter_event" in stage_config:
                        # 이벤트 필터링
                        for row in response.rows:
                            event_name = row.dimension_values[0].value
                            if stage_config["filter_event"] in event_name:
                                total_count += int(row.metric_values[0].value)
                    
                    if total_count > 0:
                        stage_data.append({
                            "stage": stage_config["name"],
                            "count": total_count,
                            "order": i
                        })
            except Exception as e:
                print(f"⚠️ 단계 '{stage_config['name']}' 조회 오류: {e}")
                continue
        
        # 정렬
        stage_data.sort(key=lambda x: x["order"])
        
        # 전환율 계산
        if stage_data:
            first_count = stage_data[0]["count"]
            for i, stage in enumerate(stage_data):
                stage["conversion_rate"] = round((stage["count"] / first_count) * 100, 1) if first_count > 0 else 0
                if i > 0:
                    prev_count = stage_data[i-1]["count"]
                    stage["step_conversion"] = round((stage["count"] / prev_count) * 100, 1) if prev_count > 0 else 0
                else:
                    stage["step_conversion"] = 100
        
        return {
            "stages": stage_data,
            "total_users": stage_data[0]["count"] if stage_data else 0,
            "final_conversions": stage_data[-1]["count"] if stage_data else 0,
            "overall_conversion": round((stage_data[-1]["count"] / stage_data[0]["count"]) * 100, 1) if stage_data and stage_data[0]["count"] > 0 else 0
        }
    
    def get_summary(self, days: int = 7):
        """전체 요약 데이터 조회"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        response = self.run_report(
            dimensions=[],
            metrics=["eventCount", "screenPageViews"],
            date_ranges=[{
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }]
        )
        
        if not response or len(response.rows) == 0:
            return {"total_events": 0, "total_page_views": 0}
        
        row = response.rows[0]
        return {
            "total_events": int(row.metric_values[0].value),
            "total_page_views": int(row.metric_values[1].value)
        }
