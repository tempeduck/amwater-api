"""Client implementation for the American Water API."""

import json
import logging
from typing import Any, Dict, List, Optional
import aiohttp

from .exceptions import (
    AmericanWaterAuthError,
    AmericanWaterConnectError,
    AmericanWaterError,
)

_LOGGER = logging.getLogger(__name__)

AUTH_SERVER = "https://auth.amwater.com/oauth2/aus29oxmv4bzpt55X5d7"
CLIENT_ID = "0oa29ovb79AWEoS8V5d7"
REDIRECT_URI = "https://mywaterv2.amwater.com/openidlogin"


class AmericanWaterAPI:
    """API client for Illinois American Water."""

    def __init__(self, session: Optional[aiohttp.ClientSession] = None) -> None:
        """Initialize the client."""
        self._session = session
        self._close_session = False
        
        self._jsessionid: str = ""
        self._auth_token: str = ""

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the client session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True
        return self._session

    async def async_login(self, username: str, password: str) -> None:
        """Authenticate with the American Water portal via Okta OIDC."""
        session = await self._get_session()
        
        # Step 1: Okta Authentication (authn)
        _LOGGER.debug("Authenticating with Okta authn API")
        try:
            async with session.post(
                "https://auth.amwater.com/api/v1/authn",
                json={"username": username, "password": password},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=15
            ) as res:
                if res.status != 200:
                    if res.status == 401:
                        raise AmericanWaterAuthError("Invalid username or password")
                    raise AmericanWaterConnectError(
                        f"Authentication server returned status: {res.status}"
                    )
                auth_data = await res.json()
                
                if auth_data.get("status") != "SUCCESS":
                    raise AmericanWaterAuthError(
                        f"Authentication failed with status: {auth_data.get('status')}"
                    )
                session_token = auth_data["sessionToken"]
        except aiohttp.ClientError as err:
            raise AmericanWaterConnectError(f"Connection error during login: {err}")
            
        # Step 2: Request OIDC Authorization Code
        _LOGGER.debug("Requesting OIDC authorization code")
        authorize_url = f"{AUTH_SERVER}/v1/authorize"
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile GroupMembership UserContext",
            "state": "state-123",
            "nonce": "nonce-456",
            "sessionToken": session_token
        }
        
        try:
            async with session.get(
                authorize_url,
                params=params,
                allow_redirects=False,
                timeout=15
            ) as res:
                if res.status != 302:
                    raise AmericanWaterConnectError(
                        f"OIDC authorization failed with status: {res.status}"
                    )
                redirect_target = res.headers.get("Location")
        except aiohttp.ClientError as err:
            raise AmericanWaterConnectError(f"Connection error during OIDC authorize: {err}")
            
        if not redirect_target or "code=" not in redirect_target:
            raise AmericanWaterAuthError("Failed to retrieve OIDC authorization code")
            
        # Step 3: Exchange code for session cookies and JWT Bearer token
        _LOGGER.debug("Exchanging authorization code for session")
        try:
            async with session.get(
                redirect_target,
                allow_redirects=False,
                timeout=15
            ) as res:
                if res.status not in (200, 302):
                    raise AmericanWaterConnectError(
                        f"Session initialization failed with status: {res.status}"
                    )
                
                # Retrieve cookies from jar
                jsessionid = ""
                auth_token = ""
                for cookie in session.cookie_jar:
                    if cookie.key == "JSESSIONID":
                        jsessionid = cookie.value
                    elif cookie.key == "mw-authenticationToken":
                        auth_token = cookie.value
                        
                self._jsessionid = jsessionid
                self._auth_token = auth_token
        except aiohttp.ClientError as err:
            raise AmericanWaterConnectError(f"Connection error during openidlogin: {err}")

        if not self._auth_token:
            raise AmericanWaterAuthError("Failed to acquire session token")

    def _get_headers(self) -> Dict[str, str]:
        """Get standard authenticated headers."""
        if not self._auth_token:
            raise AmericanWaterAuthError("Client is not authenticated. Call async_login() first.")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._auth_token}"
        }

    async def async_get_account_summary(self) -> Dict[str, Any]:
        """Fetch general details about the account."""
        session = await self._get_session()
        headers = self._get_headers()
        
        mso_body = {
            "pipelineId": "com::apporchid::cloudseer::mso::myaccountsummarypipeline",
            "requestParameters": {
                "@class": "com.apporchid.common.UIRequestParameters",
                "keyValueMap": {
                    "queryParams": None
                }
            }
        }
        
        try:
            async with session.post(
                "https://mywaterv2.amwater.com/api/mso/data",
                json=mso_body,
                headers=headers,
                timeout=15
            ) as res:
                if res.status != 200:
                    raise AmericanWaterConnectError(
                        f"Failed to fetch account summary: {res.status} {res.reason}"
                    )
                mso_data = await res.json()
                
                details_list = mso_data.get("data", [{}])[0].get(
                    "additionalInformation", {}
                ).get("IntermediaryPageDetails", [])
                
                if not details_list:
                    raise AmericanWaterError("No account summary details found in response.")
                    
                details = details_list[0]
                
                # Combine house number and street
                house = details.get("houseNumber", "").strip()
                street = details.get("street", "").strip()
                addr = f"{house} {street}".strip()
                
                return {
                    "business_partner": details.get("businessPartnerNumber"),
                    "contract_account": details.get("contractAccountNumber"),
                    "premise": details.get("premiseNumber"),
                    "address": addr,
                    "city": details.get("city"),
                    "state": details.get("state"),
                    "zip": details.get("zip"),
                    "status": details.get("contractAccountStatus"),
                    "due_date": details.get("currentBillDueDate"),
                    "total_due": details.get("totalDue", "").strip()
                }
        except aiohttp.ClientError as err:
            raise AmericanWaterConnectError(f"Connection error fetching account summary: {err}")

    async def async_get_usage_history(
        self, bp: str, contract: str, premise: str, months: int = 36
    ) -> List[Dict[str, Any]]:
        """Fetch water usage historical entries (default: 36 months)."""
        session = await self._get_session()
        headers = self._get_headers()
        
        microapp_id = "usageOverviewMonthlyChartFourYears" if months > 24 else (
            "usageOverview24MonthlyChart" if months > 12 else "usageOverview12MonthlyChart"
        )
        
        chart_body = {
            "solutionId": "com::amwater::enhancedportal::enhancedportal",
            "applicationId": "com::amwater::enhancedportal::usageoverview",
            "microApplicationId": microapp_id,
            "solutionPageId": "com::amwater::enhancedportal::landingPage",
            "renderType": "CONFIG_AND_DATA",
            "userOptions": {
                "@class": "com.apporchid.vulcanux.common.ui.data.UserOptions",
                "locale": "en-US",
                "timeZone": "America/Chicago",
                "screenWidth": 1280,
                "screenHeight": 1000,
                "orientation": 0,
                "orientationType": "Portrait"
            },
            "keyValueMap": {
                "queryParams": {
                    "businessPartnerNumber": bp,
                    "connectionContractNumber": contract,
                    "premiseId": premise,
                    "billMonth": "",
                    "limitRecords": 2,
                    "regionName": "IL",
                    "startDate": "",
                    "endDate": "",
                    "source": "",
                    "premiseStateCode": "IL",
                    "stateCode": "IL",
                    "serviceUrl": "",
                    "accountType": "",
                    "days": str(months),
                    "selectedVal": str(months)
                }
            },
            "@class": "com.apporchid.common.UIRequestParameters",
            "isDebug": False
        }
        
        try:
            async with session.post(
                "https://mywaterv2.amwater.com/api/vux/microapp",
                json=chart_body,
                headers=headers,
                timeout=15
            ) as res:
                if res.status != 200:
                    raise AmericanWaterConnectError(
                        f"Failed to fetch usage chart: {res.status} {res.reason}"
                    )
                chart_res = await res.json()
                if "response" in chart_res:
                    response_data = json.loads(chart_res["response"]) if isinstance(chart_res["response"], str) else chart_res["response"]
                else:
                    response_data = chart_res
                
                component = response_data.get("component", {})
                series = component.get("series", [])
                
                entries = []
                for s in series:
                    year = s.get("name")
                    for item in s.get("data", []):
                        month_idx = item[0]
                        value = item[1]  # Measured in hundreds of gallons
                        
                        month_str = f"{month_idx + 1:02d}"
                        date_str = f"{year}-{month_str}-01"
                        gallons = int(value * 100)
                        
                        entries.append({
                            "date": date_str,
                            "gallons": gallons
                        })
                        
                entries.sort(key=lambda x: x["date"])
                return entries
        except aiohttp.ClientError as err:
            raise AmericanWaterConnectError(f"Connection error fetching usage history: {err}")

    async def async_get_billing_history(
        self, bp: str, contract: str, premise: str
    ) -> List[Dict[str, Any]]:
        """Fetch list of recent bill statements and payments."""
        session = await self._get_session()
        headers = self._get_headers()
        
        from datetime import datetime, timedelta
        to_date = datetime.today().strftime('%Y%m%d')
        from_date = (datetime.today() - timedelta(days=3*365)).strftime('%Y%m%d')
        
        body = {
            "solutionId": "com::amwater::enhancedportal::enhancedportal",
            "applicationId": "com::amwater::enhancedportal::billingandpaymentshistorycontainerapp",
            "microApplicationId": "billingAndPaymentsHistoryTable",
            "solutionPageId": "com::amwater::enhancedportal::billingAndPaymentHistoryPage",
            "renderType": "CONFIG_AND_DATA",
            "userOptions": {
                "@class": "com.apporchid.vulcanux.common.ui.data.UserOptions",
                "locale": "en-US",
                "timeZone": "America/Chicago"
            },
            "keyValueMap": {
                "queryParams": {
                    "businessPartnerNumber": bp,
                    "connectionContractNumber": contract,
                    "contractAccNumber": contract,
                    "premiseId": premise,
                    "region": "IL",
                    "regionName": "IL",
                    "stateCode": "IL",
                    "premiseStateCode": "IL",
                    "companyCode": "1025",
                    "fromDate": from_date,
                    "toDate": to_date,
                    "billMonth": "",
                    "limitRecords": 2,
                    "days": "",
                    "selectedVal": ""
                }
            },
            "@class": "com.apporchid.common.UIRequestParameters",
            "isDebug": False
        }
        
        try:
            async with session.post(
                "https://mywaterv2.amwater.com/api/vux/microapp",
                json=body,
                headers=headers,
                timeout=15
            ) as res:
                if res.status != 200:
                    raise AmericanWaterConnectError(
                        f"Failed to fetch billing history: {res.status} {res.reason}"
                    )
                history_res = await res.json()
                if "response" in history_res:
                    response_data = json.loads(history_res["response"]) if isinstance(history_res["response"], str) else history_res["response"]
                else:
                    response_data = history_res
                data = response_data.get("component", {}).get("data", [])
                
                entries = []
                for item in data:
                    amt_str = item.get("transactionAmount", "0")
                    is_negative = "-" in amt_str
                    amt_val = float(amt_str.replace("-", "").strip())
                    amount = -amt_val if is_negative else amt_val
                    
                    # Map raw transaction types to user-friendly ones
                    raw_type = item.get("docTypeDescription", "")
                    if raw_type == "Invoicing":
                        trans_type = "Bill Issued"
                    elif raw_type == "Direct Debit":
                        trans_type = "Payment"
                    else:
                        trans_type = raw_type
                        
                    entries.append({
                        "date": item.get("postingDate"),
                        "type": trans_type,
                        "amount": amount,
                        "document_no": item.get("documentNo"),
                        "doc_id": item.get("pdfURL"),
                        "status": item.get("status")
                    })
                return entries
        except aiohttp.ClientError as err:
            raise AmericanWaterConnectError(f"Connection error fetching billing history: {err}")

    async def async_download_bill_pdf(self, doc_id: str, dest_path: str) -> None:
        """Download a bill PDF and clean the multipart MIME boundary formatting."""
        session = await self._get_session()
        headers = self._get_headers()
        
        url = f"https://mywaterv2.amwater.com/api/cloudseer/pdf/ViewBill?docId={doc_id}"
        
        try:
            async with session.get(url, headers=headers, timeout=30) as res:
                if res.status != 200:
                    raise AmericanWaterConnectError(
                        f"Failed to download PDF: {res.status} {res.reason}"
                    )
                raw_data = await res.read()
                
                # Check for multipart boundary and find %PDF start index
                pdf_magic = b"%PDF"
                start_idx = raw_data.find(pdf_magic)
                if start_idx == -1:
                    raise AmericanWaterError("Invalid bill download response: PDF markers not found.")
                    
                # Search for %%EOF
                eof_magic = b"%%EOF"
                last_eof = raw_data.rfind(eof_magic)
                
                if last_eof != -1:
                    pdf_data = raw_data[start_idx : last_eof + len(eof_magic)]
                else:
                    pdf_data = raw_data[start_idx:]
                    
                with open(dest_path, "wb") as pdf_file:
                    pdf_file.write(pdf_data)
        except aiohttp.ClientError as err:
            raise AmericanWaterConnectError(f"Connection error downloading PDF: {err}")
        except IOError as err:
            raise AmericanWaterError(f"Failed to write PDF file: {err}")

    async def async_close(self) -> None:
        """Close the underlying session if we created it."""
        if self._close_session and self._session is not None:
            await self._session.close()
            self._session = None
            self._close_session = False
