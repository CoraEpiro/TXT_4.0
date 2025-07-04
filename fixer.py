import json, re, pathlib

fixed = pathlib.Path("data_fixed.jsonl").open("w", encoding="utf-8")

with open("data.jsonl", encoding="utf-8") as f:
    for line in f:
        item = json.loads(line)
        # move item["response"] into messages
        if "response" in item:
            item["messages"].append(
                {"role": "assistant", "content": item.pop("response")}
            )
        # replace placeholder "(same system prompt)" with the real string if present
        for m in item["messages"]:
            if m["content"].startswith("(same system prompt)"):
                m["content"] = "You are an expert robot assistant. …"  # full text here
        fixed.write(json.dumps(item, ensure_ascii=False) + "\n")