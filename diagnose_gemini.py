"""
Gemini API 診斷工具
用於檢查 API Key 和可用模型
"""

import google.generativeai as genai

def diagnose_gemini_api(api_key):
    """診斷 Gemini API 連線狀況"""
    
    print("=" * 60)
    print("🔍 Gemini API 診斷工具")
    print("=" * 60)
    
    if not api_key:
        print("❌ 錯誤：未提供 API Key")
        return
    
    print(f"\n📋 API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        # 設定 API Key
        genai.configure(api_key=api_key)
        print("✅ API Key 設定成功")
        
        # 列出所有可用模型
        print("\n📦 正在獲取可用模型清單...")
        models = genai.list_models()
        
        print("\n可用的模型：")
        print("-" * 60)
        
        generative_models = []
        for model in models:
            print(f"\n模型名稱: {model.name}")
            print(f"  支援方法: {model.supported_generation_methods}")
            print(f"  顯示名稱: {model.display_name}")
            
            if 'generateContent' in model.supported_generation_methods:
                generative_models.append(model.name)
        
        print("\n" + "=" * 60)
        print(f"✅ 找到 {len(generative_models)} 個支援文字生成的模型")
        print("=" * 60)
        
        if generative_models:
            print("\n推薦使用的模型：")
            for idx, model_name in enumerate(generative_models[:5], 1):
                print(f"{idx}. {model_name}")
            
            # 測試第一個模型
            print(f"\n🧪 測試模型: {generative_models[0]}")
            test_model = genai.GenerativeModel(generative_models[0])
            response = test_model.generate_content("請用繁體中文說：測試成功")
            print(f"✅ 模型回應: {response.text}")
            
        else:
            print("❌ 沒有找到支援 generateContent 的模型")
            
    except Exception as e:
        print(f"\n❌ 發生錯誤: {str(e)}")
        import traceback
        print("\n詳細錯誤訊息:")
        print(traceback.format_exc())
        
        print("\n💡 可能的解決方案:")
        print("1. 檢查 API Key 是否正確")
        print("2. 確認 API Key 已啟用 Gemini API")
        print("3. 更新套件: pip install --upgrade google-generativeai")
        print("4. 檢查網路連線")
        print("5. 前往 https://aistudio.google.com/app/apikey 確認 Key 狀態")

if __name__ == "__main__":
    import sys
    
    print("\n請輸入你的 Gemini API Key:")
    api_key = input().strip()
    
    if api_key:
        diagnose_gemini_api(api_key)
    else:
        print("❌ 未輸入 API Key")
