"""
AIcentralv2 - Modelos de dados da aplicação
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class User:
    """Modelo de Usuário"""
    id: Optional[int] = None
    nome: str = ''
    email: str = ''
    idade: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self):
        """Converte objeto para dicionário"""
        return {
            'id': self.id,
            'nome': self.nome,
            'email': self.email,
            'idade': self.idade,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def from_dict(data):
        """Cria objeto a partir de dicionário"""
        return User(
            id=data.get('id'),
            nome=data.get('nome', ''),
            email=data.get('email', ''),
            idade=data.get('idade', 0),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def __repr__(self):
        return f"<User {self.nome} ({self.email})>"


@dataclass
class Product:
    """Modelo de Produto"""
    id: Optional[int] = None
    nome: str = ''
    preco: float = 0.0
    estoque: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'preco': float(self.preco),
            'estoque': self.estoque,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f"<Product {self.nome} - R$ {self.preco}>"


@dataclass
class AuthUser:
    """Modelo de Usuário de Autenticação"""
    id: Optional[int] = None
    username: str = ''
    nome_completo: str = ''
    created_at: Optional[datetime] = None
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nome_completo': self.nome_completo,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"<AuthUser {self.username}>"