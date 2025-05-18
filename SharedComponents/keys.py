
def loadPrivateKey():
    with open('SharedComponents/private.pem', 'rb') as f:
        return f.read()         # raw PEM

def loadPublicKey():
    with open('SharedComponents/public.pem', 'rb') as f:
        return f.read()
