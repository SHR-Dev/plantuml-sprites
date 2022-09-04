from PIL import Image
from cairosvg import svg2png
from hashlib import sha1
from jinja2 import Template
from yaml import safe_load
import os, sys, re, shutil
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile

from queue import Queue
from threading import Thread

num_threads = 4
force = False

def get_hash(filepath):
    BLOCKSIZE = 65536
    hasher = sha1()
    with open(filepath, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
    return hasher.hexdigest()


def is_white(rgb): return sum(rgb) >= 750
def is_black(rgb): return sum(rgb) <= 15 
def is_grey(rgb): 
    r,g,b = rgb
    return all([
        abs(r-g)<=5,
        abs(b-g)<=5,
        abs(b-r)<=5,
    ])

def get_primary_color(img):
    img = img.convert('RGB').convert('P', colors=255)
    q = img.quantize(colors=6,method=2)
    c = q.getpalette()[:12]
    colors = [(c[i],c[i+1],c[i+2]) for i in range(len(c))[::3]]
    for c in colors:
        if not is_grey(c):
            return f"#{hex(c[0])[2::].rjust(2, '0')}{hex(c[1])[2::].rjust(2, '0')}{hex(c[2])[2::].rjust(2, '0')}"
        else:
            return "#000000"

def bilevel(img):
    thresh = 200
    fn = lambda x : 255 if x > thresh else 0
    return img.convert('L').point(fn, mode='1')

def resize(img, size=(256,256) ):
    image = img.convert("RGBA")
    image.thumbnail(size)
    new_image = Image.new("RGBA", image.size, "WHITE")
    new_image.paste(image, (0, 0), image)
    nw,nh = new_image.size 
    tw,th = size
    if nw < tw and nh < th:
        r = max(tw/nw,th/nh)
        new_image = new_image.resize((int(nw*r),int(nh*r)))
    return new_image

def make_sprite(name, img):
    with NamedTemporaryFile(suffix='.png', dir='/dev/shm') as tmp:
        img.save(tmp.name)
        cmd = [
            '/usr/local/openjdk-11/bin/java',
            '-Djava.net.useSystemProxies=true',
            '-Djava.awt.headless=true',
            '-jar', '/plantuml/plantuml.jar',
            '-encodesprite 4z',
            '-nbthread 1',
            tmp.name
        ]
        p = subprocess.run(
            " ".join(cmd), shell=True,
            stdout = subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        return p.stdout.decode("utf-8").replace(Path(tmp.name).stem,name)

def export_sprite(name, hash, sprite, color):
    with open('templates/sprite.j2') as template_file:
        template = Template(template_file.read())
        return template.render(
            name=name, hash=hash, sprite=sprite, color=color
        )

def get_name(src, group="", name_filters=[], name_append=''):
    # if group: name = f"{group}_{Path(src).stem}".lower()
    # else:     name = f"{Path(src).stem}".lower()
    name = f"{Path(src).stem}".lower()
    for filter in name_filters:
        name = re.sub(filter,"",name)
    name = re.sub('[-\(\)\&,\.\/\\s]','',name)
    return name+name_append

def is_icon(file, path_filters):
    def is_image(file):
        try:
            Image.open(file)
            return True
        except Exception as e:
            try:
                with open(file) as f:
                    if '<svg' in f.read(): return True
            except Exception as e:
                return False
    filters = [
        os.stat(file).st_size > 0,
        os.path.isfile(file),
        is_image(file)
    ]
    filters += [bool(re.search(filt, file)) for filt in path_filters]
    return all(filters)
    
def convert(src, name, group="", root='dist'):
    try:
        img = Image.open(src)
    except:
        # print(f"Failed Image, trying SVG on {src}")
        try:
            with NamedTemporaryFile(suffix='.svg', dir='/dev/shm') as out:
                with open(src, 'rb') as svg:
                    svg2png(bytestring=svg.read(),write_to=out.name)
                img = Image.open(out.name)
        except:
            print("Failed in SVG reading on {src}")
    dest = f"{os.path.join(root,group,name)}.iuml"
    hash = get_hash(src)
    try:
        current_hash = open(dest).readlines()[0][1::].strip()
        if hash == current_hash and not force: return
    except: pass 
    sprite = export_sprite(
        name = name,
        color = get_primary_color(img),
        hash = hash,
        sprite = make_sprite(name, resize(img))
    )
    with open(dest, 'w') as out:
        out.write(sprite)

def process(q):
    while not q.empty():
        task = q.get()
        convert(*task)
        print(f"{q.qsize()} tasks left")
        q.task_done()

root = 'dist'
q = Queue(maxsize=0)
if len(sys.argv) != 2:
    print(f"{sys.argv[0]} <conf.yaml>")
    sys.exit(1)
conf_file = sys.argv[1]
with open(conf_file) as f:
    sources = safe_load(f)
for source in sources:
    group = source.get('name','')
    os.makedirs(os.path.join(root,group), exist_ok=True)
    paths = source.get('paths','.')
    files = []
    for path in paths:
        files += [os.path.join(dp, f) for dp, dn, fn in os.walk(os.path.expanduser(path)) for f in fn
            if is_icon(os.path.join(dp, f), source.get('path_filters',['^.*$'])) ]
    for file in files:
        name = get_name(file, group, source.get('name_filters', []), source.get('name_append',''))
        q.put((file, name, group, root))

# threads = []
# for i in range(num_threads):
#     worker = Thread(target=process, args=(q,))
#     threads.append(worker)
#     worker.start()

# for x in threads:
#     x.join()

def dir_walk(directory):
    paths = []
    items = [os.path.join(directory,f) for f in os.listdir(directory)]
    for item in items:
        if os.path.isdir(item):
            paths += dir_walk(item)

def build_indices(directory):
    catalogs = []
    sprites = []
    items = [os.path.join(directory,f) for f in os.listdir(directory)]
    for item in items:
        if os.path.isdir(item):
            build_indices(item)
            catalogs += [item]
        elif os.path.isfile(item):
            sprites += [item]
    with open('templates/index.j2') as template_file:
        template = Template(template_file.read())
        with open(os.path.join(directory,'index.iuml'), 'w') as index:
            index.write(template.render(
                groups=catalogs, files=[Path(f).name for f in sprites if f.endswith('.iuml') and not f.endswith('index.iuml')]
            ))
    with open('templates/catalog.j2') as template_file:
        template = Template(template_file.read())
        with open(os.path.join(directory,'catalog.puml'), 'w') as catalog:
            catalog.write(template.render(
                groups=[g.replace(directory,'') for g in catalogs], 
                files=[Path(f).stem for f in sprites if f.endswith('.iuml') and not f.endswith('index.iuml')], 
                root=Path(directory).parts[-1]
            ))
    return

def render(puml):
    print(f"Rendering {puml}")
    cmd = [
        '/usr/local/openjdk-11/bin/java',
        '-Xmx2048m',
        '-Djava.net.useSystemProxies=true',
        '-Djava.awt.headless=true',
        '-DPLANTUML_LIMIT_SIZE=16384',
        '-jar', '/plantuml/plantuml.jar',
        puml
    ]
    try:
        subprocess.run(" ".join(cmd), shell=True, stdout = subprocess.PIPE, stderr=subprocess.PIPE)
    except:
        print(f"Failed to render {puml}")

def render_catalogs(root):
    for f in os.listdir(root):
        fq = os.path.join(root,f)
        if os.path.isdir(fq):
            render_catalogs(fq)
        elif f.endswith('.puml'):
            render(fq)

for source in sources:
    name = source.get('name')
    source_root = os.path.join(root,name)
    build_indices(source_root)
    render_catalogs(source_root)
    shutil.copy(
        os.path.join(root,name,'catalog.png'),
        os.path.join(root,f"{name}.png")
    )


## Generate Indices
# for source in sources:
#     source_root = os.path.join(root,source)
#     build_indices(source_root)

# for dp, dn, fn in os.walk(root, topdown=True):
#     files = [f for f in fn if f.endswith('iuml') and f != 'index.iuml']
#     with open('templates/index.j2') as template_file:
#         template = Template(template_file.read())
#         with open(os.path.join(dp,'index.iuml'), 'w') as index:
#             index.write(template.render(
#                 files=files, children=[d for d in dn if os.path.exists(os.path.join(dp,d,'index.puml'))]
#             ))
#     with open('templates/catalog.j2') as template_file:
#         template = Template(template_file.read())
#         with open(os.path.join(dp,'catalog.puml'), 'w') as index:
#             print(f"creating {os.path.join(dp,'catalog.puml')}")
#             index.write(template.render(
#                 groups=[d for d in dn if os.path.exists(os.path.join(dp,d,'catalog.puml'))], files=files, root=dp.replace(root+'/','')
#             ))
#         cmd = [
#             '/usr/local/openjdk-11/bin/java',
#             '-Djava.net.useSystemProxies=true',
#             '-Djava.awt.headless=true',
#             '-DPLANTUML_LIMIT_SIZE=8192',
#             '-jar', '/plantuml/plantuml.jar',
#             f"{os.path.join(dp,'catalog.puml')}"
#         ]
#         try:
#             check_output(
#                 " ".join(cmd), shell=True
#             )
#         except:
#             pass
