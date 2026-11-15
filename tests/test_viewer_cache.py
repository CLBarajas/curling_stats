"""The local viewer's server: a browser must not keep a run's files on a guess."""
import functools
import http.client
import http.server
import threading

from curling_score import viewer


def test_every_file_is_revalidated_and_an_unchanged_one_costs_no_body(tmp_path):
    (tmp_path / "timeline.json").write_text('{"games": []}')
    handler = functools.partial(viewer.ViewerHandler, directory=str(tmp_path))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        conn.request("GET", "/timeline.json")
        first = conn.getresponse()
        assert first.status == 200 and first.read() == b'{"games": []}'
        assert first.getheader("Cache-Control") == "no-cache"
        conn.request("GET", "/timeline.json",
                     headers={"If-Modified-Since": first.getheader("Last-Modified")})
        again = conn.getresponse()
        assert again.status == 304 and again.read() == b""
        assert again.getheader("Cache-Control") == "no-cache"
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
