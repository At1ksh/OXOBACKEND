import os
import json
import shutil
import uuid
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

router = APIRouter()

# Base paths
BASE_DATA_DIR = "data"  # Relative to project root
REFERENCE_DIR = os.path.join(BASE_DATA_DIR, "reference_images")
MODELS_DIR = os.path.join(BASE_DATA_DIR, "models")
MAIN_IMAGES_DIR = os.path.join(BASE_DATA_DIR, "main_images")
CASE_SPECS_FILE = os.path.join(BASE_DATA_DIR, "CaseSpecifications.json")

def to_relative_url(abs_path: str):
    """Convert an absolute file path to a relative FastAPI static URL."""
    # Convert to forward slashes and make relative to data directory
    if os.path.isabs(abs_path):
        rel_path = os.path.relpath(abs_path, os.path.abspath(BASE_DATA_DIR)).replace("\\", "/")
        return f"data/{rel_path}"
    else:
        # Already relative, just ensure it starts with data/
        clean_path = abs_path.replace("\\", "/")
        if not clean_path.startswith("data/"):
            return f"data/{clean_path}"
        return clean_path

@router.post("/recievenewkspec")
async def recieve_new_kspec(kspec_metadata: str = Form(...)):
    try:
        kspec_data = json.loads(kspec_metadata)
        model_code = kspec_data.get("modelCode", f"MODEL_{uuid.uuid4().hex[:6]}")

        # === Ensure folders exist ===
        os.makedirs(REFERENCE_DIR, exist_ok=True)
        os.makedirs(MODELS_DIR, exist_ok=True)
        os.makedirs(MAIN_IMAGES_DIR, exist_ok=True)

        # === Copy Main Image ===
        if kspec_data.get("mainImagePath") and os.path.exists(kspec_data["mainImagePath"]):
            target_dir = os.path.join(MAIN_IMAGES_DIR, model_code)
            os.makedirs(target_dir, exist_ok=True)

            source_path = kspec_data["mainImagePath"]
            target_path = os.path.join(target_dir, os.path.basename(source_path))
            
            print(f"📸 Copying main image: {source_path} → {target_path}")
            shutil.copy2(source_path, target_path)
            kspec_data["mainImagePath"] = to_relative_url(target_path)
            print(f"📸 Main image URL: {kspec_data['mainImagePath']}")
        else:
            print(f"⚠️ Main image not found or not specified: {kspec_data.get('mainImagePath')}")

        # === Handle Components ===
        all_subcomponents = []

        for comp in kspec_data.get("components", []):
            comp_name = comp["name"].replace(" ", "")
            ref_dir = os.path.join(REFERENCE_DIR, model_code, comp_name)
            model_dir = os.path.join(MODELS_DIR, model_code, comp_name)
            os.makedirs(ref_dir, exist_ok=True)
            os.makedirs(model_dir, exist_ok=True)

            # --- Copy Component Main Image ---
            if comp.get("mainImage") and os.path.exists(comp["mainImage"]):
                source_path = comp["mainImage"]
                target_path = os.path.join(ref_dir, os.path.basename(source_path))
                
                print(f"🖼️ Copying component image: {source_path} → {target_path}")
                shutil.copy2(source_path, target_path)
                comp["mainImage"] = to_relative_url(target_path)
                print(f"🖼️ Component image URL: {comp['mainImage']}")
            else:
                print(f"⚠️ Component main image not found: {comp.get('mainImage')}")

            # --- Copy Model Files ---
            pipeline = comp.get("pipelineConfig", {})
            for model_key in ["YOLO_DONTDETECT", "YOLO_ROIDETECT", "YOLO_SIMPLEDETECT"]:
                model_path = pipeline.get(model_key)
                if model_path and model_path != "SKIP" and os.path.exists(model_path):
                    source_path = model_path
                    target_path = os.path.join(model_dir, os.path.basename(source_path))
                    
                    print(f"🤖 Copying model {model_key}: {source_path} → {target_path}")
                    shutil.copy2(source_path, target_path)
                    # For models, use relative path (not URL) for file system access
                    pipeline[model_key] = os.path.relpath(target_path).replace("\\", "/")
                    print(f"🤖 Model path updated: {pipeline[model_key]}")
                elif model_path and model_path != "SKIP":
                    print(f"⚠️ Model file not found: {model_path}")

            # --- Copy Subcomponents ---
            for sub in comp.get("subComponents", []):
                if sub.get("referenceImage") and os.path.exists(sub["referenceImage"]):
                    target_path = os.path.join(ref_dir, os.path.basename(sub["referenceImage"]))
                    shutil.copy2(sub["referenceImage"], target_path)
                    sub["referenceImage"] = to_relative_url(target_path)
                all_subcomponents.append(sub)

        # === Load existing CaseSpecifications.json ===
        if os.path.exists(CASE_SPECS_FILE):
            with open(CASE_SPECS_FILE, "r", encoding="utf-8") as f:
                case_specs = json.load(f)
        else:
            case_specs = {}

        # === Append or Update Model ===
        case_specs[model_code] = {
            "modelName": kspec_data["modelName"],
            "variantName": kspec_data["variantName"],
            "totalInterior": kspec_data["totalInterior"],
            "totalExterior": kspec_data["totalExterior"],
            "totalLoose": kspec_data["totalLoose"],
            "mainImagePath": kspec_data["mainImagePath"],
            "components": kspec_data["components"],
            "subComponents": all_subcomponents
        }

        # === Save back to CaseSpecifications.json ===
        with open(CASE_SPECS_FILE, "w", encoding="utf-8") as f:
            json.dump(case_specs, f, indent=2, ensure_ascii=False)

        return JSONResponse({
            "success": True,
            "message": "KSpec uploaded and appended to CaseSpecifications.json successfully",
            "model_code": model_code,
            "components_count": len(kspec_data.get("components", [])),
            "total_models": len(case_specs),
            "case_specs_file": CASE_SPECS_FILE.replace("\\", "/")
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
