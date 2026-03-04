import base64
import io

from PIL import Image

from .flow import _zip_images_dict, _process_babylon_return


def make_dummy_png(color=(255, 0, 0)):
    img = Image.new("RGB", (10, 10), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_zip_images_dict_and_thumb(tmp_path):
    # create two dummy images and encode as data URL
    img1 = make_dummy_png((10, 20, 30))
    img2 = make_dummy_png((40, 50, 60))
    url1 = "data:image/png;base64," + base64.b64encode(img1).decode('ascii')
    url2 = "data:image/png;base64," + base64.b64encode(img2).decode('ascii')
    d = {"first": url1, "second": url2}
    zip_bytes = _zip_images_dict(d, thumb=False)
    # basic sanity: bytes start with PK header
    assert zip_bytes[:2] == b"PK"
    zip_thumb = _zip_images_dict(d, thumb=True)
    # still a zip
    assert zip_thumb[:2] == b"PK"
    # should not be identical (filenames differ)
    assert zip_bytes != zip_thumb


def test_process_babylon_return_creates_thumbnails():
    img = make_dummy_png((123, 222, 111))
    url = "data:image/png;base64," + base64.b64encode(img).decode('ascii')
    editor_string = '{"view1": "%s"}' % url
    caps, thumbs = _process_babylon_return(editor_string)
    assert "view1" in caps
    assert caps["view1"].startswith("data:image/png;base64,")
    # thumbnail should be base64 encoded smaller image
    assert "view1" in thumbs
    thumb_data = base64.b64decode(thumbs["view1"])
    # small pillow can open it
    Image.open(io.BytesIO(thumb_data))

