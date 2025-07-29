import os
import shutil
import openpyxl
import json
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from datetime import datetime

router = APIRouter()

RESULTS_DIR = "results"
WHO_DATA_FILE = "data/WhoData.xlsx"


@router.post("/finalize_audit")
async def finalize_audit(
    full_vin: str = Form(...),
    total_ok: int = Form(...),
    total_notok: int = Form(...),
    total_pending: int = Form(...),
    component_statuses: str = Form(...)  # ✅ JSON string from frontend
):
    try:
        # ✅ 1. Rename Folder from (Ongoing) → (Done)
        ongoing_folder = os.path.join(RESULTS_DIR, f"{full_vin} (Ongoing)")
        done_folder = os.path.join(RESULTS_DIR, f"{full_vin} (Done)")

        if os.path.exists(ongoing_folder):
            shutil.move(ongoing_folder, done_folder)
        elif not os.path.exists(done_folder):
            return JSONResponse({"status": "error", "message": "No ongoing folder found"}, status_code=400)

        # ✅ 2. Update Excel File
        wb = openpyxl.load_workbook(WHO_DATA_FILE)
        sheet = wb.active

        # Find the row with the FullVin and update the status
        for row in sheet.iter_rows(min_row=2, values_only=False):
            if row[0].value == full_vin:
                if total_pending > 0:
                    row[4].value = "Incomplete"
                elif total_notok == 0:
                    row[4].value = "Finished (OK)"
                else:
                    row[4].value = "Finished (NOT OK)"
                break

        wb.save(WHO_DATA_FILE)

        # ✅ 3. Write Final Summary to a file
        component_data = json.loads(component_statuses)
        current_time = datetime.now()
        timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
        day_name = current_time.strftime("%A")
        
        # ✅ Determine final verdict based on pending and notok counts
        if total_pending > 0:
            final_verdict_text = "INCOMPLETE"
        elif total_notok == 0:
            final_verdict_text = "OK"
        else:
            final_verdict_text = "NOT OK"
        
        summary_lines = [
            "Final Audit Summary",
            "===================",
            f"Audit Completed: {timestamp}",
            f"Day: {day_name}",
            "",
            f"Full VIN: {full_vin}",
            f"Total OK: {total_ok}",
            f"Total NOT OK: {total_notok}",
            f"Total Pending: {total_pending}",
            f"Final Verdict: {final_verdict_text}",
            "",
            "Detailed Component Status:",
            "========================="
        ]
        
        # ✅ Add detailed component breakdown
        for category, components in component_data.items():
            summary_lines.append(f"\n[{category.upper()}]")
            for component_name, status in components.items():
                status_display = status.upper()
                summary_lines.append(f"  - {component_name}: {status_display}")
        
        summary_text = "\n".join(summary_lines)

        summary_file_path = os.path.join(done_folder, "FinalSummary.txt")
        with open(summary_file_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        return JSONResponse({
            "status": "success",
            "message": "Audit finalized successfully",
            "final_verdict": final_verdict_text
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
