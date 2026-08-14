import os
import time
from src.backend.memory import init_db, get_connection, insert_watch_rule
from src.backend.watcher import start_watcher

def run_smoke_test():
    init_db()
    observer = start_watcher()
    
    # 1. Create rule
    watch_dir = os.path.normcase(os.path.realpath(r"D:\Lithe\tests"))
    rule_id = insert_watch_rule(watch_dir, "*.e2e.txt", "summarize")
    print(f"Created rule {rule_id} for {watch_dir} with pattern *.e2e.txt")
    
    # 2. Drop matching file
    test_file = os.path.join(watch_dir, "smoke_test.e2e.txt")
    with open(test_file, "w") as f:
        f.write("This is an end-to-end integration smoke test document. It should be summarized.")
    print(f"Created file at {test_file}")
    
    # 3. Wait for watcher debounce (1s) + LLM summarization (~3s)
    print("Waiting for watcher and summarization (15s)...")
    time.sleep(15)
    
    # 4. Check DB
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM auto_summaries WHERE rule_id = ?", (rule_id,))
        row = cursor.fetchone()
        if row:
            print("DB ROW FOUND IN auto_summaries:")
            print(dict(row))
        else:
            print("NO DB ROW FOUND IN auto_summaries!")
            cursor.execute("SELECT * FROM action_history WHERE tool_name = 'watch_rule_summary' ORDER BY id DESC LIMIT 1")
            err_row = cursor.fetchone()
            if err_row:
                print("ACTION HISTORY LOG:")
                print(dict(err_row))
            
    # Cleanup
    try:
        if observer:
            observer.stop()
            observer.join()
        if os.path.exists(test_file):
            os.remove(test_file)
        
        # Soft delete the rule to avoid polluting DB
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE watch_rules SET active = 0 WHERE id = ?", (rule_id,))
            conn.commit()
    except Exception as e:
        print(f"Cleanup error: {e}")

if __name__ == "__main__":
    run_smoke_test()
