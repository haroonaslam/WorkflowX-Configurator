import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from detailer_x.progress import message, stage_updates, report, prefix


def test_readable_messages():
    assert message("face","processing",2,12,"Image 1/2") == "[2/12] Face detailer — Running · Image 1/2"
    assert "Reused cached result" in message("grain","cached",8,12)
    assert "Skipped (disabled)" in message("foot","bypassed",6,12)
    assert "Failed · missing file" in message("face","failed",2,12,"missing file")
    assert "Cancelled" in message("face","cancelled",2,12)


def test_nested_progress_contexts_cleanup_after_error():
    import pytest
    outer=[];inner=[]
    with stage_updates(outer.append):
        prefix("Image 1/2")
        report("Detecting")
        with pytest.raises(RuntimeError):
            with stage_updates(inner.append):
                prefix("region 1/3")
                report("Sampling step 1/15")
                raise RuntimeError("test")
        report("Done")
    report("Must not leak")
    assert outer==["Image 1/2 · Detecting","Image 1/2 · Done"]
    assert inner==["region 1/3 · Sampling step 1/15"]
