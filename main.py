#!/usr/bin/env python3
"""CLI and verification script for the amwater-api Python library."""

import asyncio
import json
import os
import sys
from dotenv import dotenv_values

from amwater_api import AmericanWaterAPI, AmericanWaterError


async def main():
    # Load credentials
    config = dotenv_values(".env")
    secrets_path = "../secrets.env"
    if os.path.exists(secrets_path):
        config.update(dotenv_values(secrets_path))
    elif os.path.exists("secrets.env"):
        config.update(dotenv_values("secrets.env"))
        
    username = config.get("AMWATER_USERNAME")
    password = config.get("AMWATER_PASSWORD")
    
    if not username or not password:
        print("Error: AMWATER_USERNAME and AMWATER_PASSWORD must be configured in .env or secrets.env")
        sys.exit(1)

    print("Initializing AmericanWaterAPI...")
    api = AmericanWaterAPI()
    
    try:
        print("Logging in to Illinois American Water portal...")
        await api.async_login(username, password)
        print("Login successful!\n")
        
        print("Retrieving Account Summary...")
        summary = await api.async_get_account_summary()
        print("Account Summary:")
        print(json.dumps(summary, indent=2))
        print()
        
        bp = summary["business_partner"]
        contract = summary["contract_account"]
        premise = summary["premise"]
        
        print(f"Retrieving 36 Months Consumption History for Premise {premise}...")
        history = await api.async_get_usage_history(bp, contract, premise, months=36)
        print(f"Found {len(history)} historical usage entries:")
        # Print first few and last few entries
        if len(history) > 10:
            for entry in history[:5]:
                print(f"  {entry['date']}: {entry['gallons']:,} gallons")
            print("  ...")
            for entry in history[-5:]:
                print(f"  {entry['date']}: {entry['gallons']:,} gallons")
        else:
            for entry in history:
                print(f"  {entry['date']}: {entry['gallons']:,} gallons")
        print()
        
        print("Retrieving Billing and Payment History...")
        billing = await api.async_get_billing_history(bp, contract, premise)
        print(f"Found {len(billing)} billing history entries. Latest transactions:")
        for item in billing[:5]:
            print(f"  {item['date']} - {item['type']}: ${item['amount']:.2f} (Status: {item['status'] or 'N/A'}, DocID: {item['doc_id'] or 'N/A'})")
        print()
        
        # Download the latest PDF bill if any exists
        latest_bills = [b for b in billing if b["type"] == "Bill Issued" and b["doc_id"]]
        if latest_bills:
            latest_bill = latest_bills[0]
            pdf_filename = f"latest_bill_{latest_bill['date']}.pdf"
            print(f"Downloading latest bill PDF ({latest_bill['date']}) to {pdf_filename}...")
            await api.async_download_bill_pdf(latest_bill["doc_id"], pdf_filename)
            if os.path.exists(pdf_filename):
                size = os.path.getsize(pdf_filename)
                print(f"Success! Saved PDF ({size:,} bytes)")
                
                # Check for PDF magic bytes
                with open(pdf_filename, "rb") as f:
                    magic = f.read(4)
                print(f"PDF magic bytes verify: {magic == b'%PDF'}")
            else:
                print("Error: PDF file was not created.")
        else:
            print("No downloadable bills found.")
            
    except AmericanWaterError as err:
        print(f"API Error occurred: {err}")
        sys.exit(1)
    finally:
        await api.async_close()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
