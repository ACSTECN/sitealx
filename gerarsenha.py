import bcrypt

senha = input("Digite a senha: ").encode("utf-8")
hash_senha = bcrypt.hashpw(senha, bcrypt.gensalt())

print("\nHash bcrypt:")
print(hash_senha.decode("utf-8"))